#!/usr/bin/env bash
#
# RA workspace architecture guard.
#
# Verifies the frozen layer rules of the RA Software Platform:
#
#   Bootstrap
#      │
#      ▼
#     SySS
#      │
#      ▼
#  Persistence
#      │
#      ▼
#    Common
#
# Rules enforced:
#
#   1. Every layer may only depend on crates strictly below it (acyclic
#      downward flow — a cycle would require an edge going both ways).
#   2. The future Frontend / Bootstrap entry binary (`software`) must never
#      directly depend on Persistence, Memory, Runtime or Compiler.
#   3. SySS must never depend on Frontend, IDE, Runtime or Compiler.
#   4. Bootstrap talks to lower layers exclusively through SySS.
#   5. Persistence and Memory are leaves above Common only.
#
# Usage:   scripts/check-architecture.sh
# Exit:    0 = policy holds, 1 = violation(s) found.
#
# CI-ready: run `bash scripts/check-architecture.sh` in the workspace root.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# ── Layer table ────────────────────────────────────────────────────────────
# Rank = position in the stack (0 is the foundation). A crate may only depend
# on crates with a strictly lower rank. Add new crates here, never weaken a
# rule.
declare -A RANK=(
  [ra-common]=0
  [ra-persistence]=1
  [ra-memory]=1
  [ra-syss]=2
  [ra-bootstrap]=3
  [software]=4
)

# Explicitly forbidden direct dependencies, per layer.
# Values are space-separated crate names; entries may reference crates that
# do not exist yet (runtime, compiler, ide, database, frontend) so the guard
# already protects the frozen boundaries before those crates are created.
declare -A FORBIDDEN=(
  # Future Frontend / Bootstrap entry binary: never touches storage, memory
  # or execution layers directly (rule 2).
  [software]="ra-persistence ra-memory ra-runtime ra-compiler ra-ide ra-database"
  # Bootstrap reaches lower layers exclusively through SySS (rule 4).
  [ra-bootstrap]="ra-persistence ra-memory ra-runtime ra-compiler ra-ide ra-database"
  # SySS is the backbone; never reaches into the outer layers (rule 3).
  [ra-syss]="ra-bootstrap ra-memory ra-runtime ra-compiler ra-ide ra-database ra-frontend"
  # Persistence is a leaf above Common only (rule 5).
  [ra-persistence]="ra-memory ra-syss ra-bootstrap ra-runtime ra-compiler ra-ide ra-database ra-frontend software"
  # Memory is a leaf above Common only (rule 5).
  [ra-memory]="ra-persistence ra-syss ra-bootstrap ra-runtime ra-compiler ra-ide ra-database ra-frontend software"
  # Common is the foundation: no dependencies at all.
  [ra-common]="ra-persistence ra-memory ra-syss ra-bootstrap ra-runtime ra-compiler ra-ide ra-database ra-frontend software"
)

errors=0
warn() { echo "ERROR: $*" >&2; errors=$((errors + 1)); }

# ── Collect crates and path-dependency edges ───────────────────────────────
# Each edge is recorded as "dependent|dependency".
declare -a EDGES=()
declare -a CRATES=()

for manifest in Cargo.toml software/Cargo.toml software/*/Cargo.toml; do
  [ -f "$manifest" ] || continue

  # The workspace root Cargo.toml has no [package] section; skip it.
  name="$(sed -n 's/^name = "\(.*\)"/\1/p' "$manifest" | head -n1)"
  [ -n "$name" ] || continue
  CRATES+=("$name")

  # Path dependencies inside [dependencies], [dev-dependencies] and
  # [build-dependencies] sections. Supports the single-line table form
  # `ra-common = { path = "../common" }`.
  deps="$(awk '
    /^\[/ {
      insection = ($0 ~ /dependencies\]/);
      next
    }
    insection && $0 ~ /^[A-Za-z0-9_-]+[[:space:]]*=[[:space:]]*\{/ && $0 ~ /path[[:space:]]*=/ {
      split($0, a, "=");
      key = a[1];
      gsub(/[[:space:]]/, "", key);
      print key
    }
  ' "$manifest")"

  for dep in $deps; do
    EDGES+=("$name|$dep")
  done
done

# ── Verify every edge ───────────────────────────────────────────────────────
for edge in "${EDGES[@]}"; do
  dependent="${edge%%|*}"
  dep="${edge##*|}"

  if [ -z "${RANK[$dependent]+x}" ]; then
    warn "crate '$dependent' is missing from the layer table (RANK) in scripts/check-architecture.sh"
    continue
  fi
  if [ -z "${RANK[$dep]+x}" ]; then
    warn "$dependent declares a path dependency on '$dep', which is not in the layer table"
    continue
  fi

  if [ "${RANK[$dependent]}" -le "${RANK[$dep]}" ]; then
    warn "$dependent must not depend on $dep (same or higher layer; layer ranks must strictly decrease)"
  fi

  if [[ " ${FORBIDDEN[$dependent]:-} " == *" $dep "* ]]; then
    warn "$dependent must never directly depend on $dep"
  fi
done

# ── Report ──────────────────────────────────────────────────────────────────
if [ "$errors" -ne 0 ]; then
  echo
  echo "Architecture check FAILED: $errors violation(s)." >&2
  exit 1
fi

echo "Architecture check passed: ${#CRATES[@]} crates, ${#EDGES[@]} dependency edge(s) verified."
