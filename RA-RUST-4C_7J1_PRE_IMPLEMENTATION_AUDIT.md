# RA-RUST-4C — PHASE 7J.1 PRE-IMPLEMENTATION CONTRACT AUDIT

**Date:** 2026-08-15
**Scope:** Audit only — no code modified. `ra-gateway`, `ra-memory`, `ra-persistence`, `ra-common`, `ra-syss` all untouched.
**Question:** What contract is required for `Execution Manager → ra-memory → ProgramSpace`, and can Phase 7J.1 proceed against the frozen memory architecture?

---

## 1. Sources inspected

| Source | What it established |
|---|---|
| `software/gateway/src/{lib.rs, gateway.rs, execution.rs, error.rs}` | The frozen Phase 7J contract (identity, request/result/lifecycle vocabularies, `Gateway` trait). |
| `software/memory/src/*.rs` (all 13 files) | The complete frozen memory implementation: `MemoryManager` (+Config/`ShutdownReport`/`SpaceUsage`), `ProgramSpace` (+`LoadedModule`/`ModuleId`/`ModuleRecord`/`CodeMapEntry`/`CodeMapIter`), `ModuleTable`, `ActiveSpace` (+`CellId`/`ScopeId`/`ActiveRecord`/Mini-Log), `EntitySpace` (+`EntityCellId`), `ValueList`/`Value`/`ValueStorage`, `LocalEntityResolver`, `GlobalEntityArea`, `LogicalAddress`, `SpaceKind`/`SpaceId`/`SpaceRecord`, `Error` (16 variants). |
| `software/memory/Cargo.toml` | `ra-memory → ra-common` only (leaf, frozen). |
| `docs/architecture.md` | Layer rules 1–6; the gateway attach point ("The future RA Core Gateway attaches behind the backbone"); `ra-syss` must never depend on runtime/compiler/memory (rule 3). |
| `docs/RA_Forensic_Audit_Report_V1.md` | Memory is **FROZEN (3/3B/3C/3D-1..3D-5), IMPLEMENTED-UNINTEGRATED, consumers: NONE**; "waiting for the Execution Manager/Runtime to consume it through the future RA Core Gateway". |
| `docs/RA_Program_Space_V1.docx` (FROZEN) | PS = Module Table/Metadata + REI Instruction Area + Constant Area + Code Map; `.ra → RA Core → RA IR → REI → Program Space → RA Execution`; REI encoding **open**; bytecode **not** frozen; PS holds no AST/IR/values/calls. |
| `docs/RA_Execution_Workflow_Architecture_Frozen_V1.docx` (FROZEN) | Run → LPM → **Freeze Snapshot** → Execution Manager → (Interpret | Compile→Compiler) → **Runtime Loader** → PS → AS → ES → WS → RS → Program Ends → **Destroy Runtime Memory** → Return Result. **Runtime Loader is the only component that populates runtime memory.** |
| `software/persistence/src/snapshot.rs`, `lpm.rs` | `FreezeSnapshot` lives in **ra-persistence**, not ra-memory: immutable copy of **source text** + FNV-1a checksum + `ProgramMeta`; `verify_integrity()`; produced by `LiveProgram::freeze()`. |
| `software/syss/src/pss.rs` | `.raf` codec exists: `Pss::serialize_snapshot` / `deserialize_snapshot`. |
| `documentation/`, `specifications/` | Empty directories — no additional memory docs. |

---

## 2. Compatibility matrix

| Phase 7J contract item | ra-memory counterpart | Compatible? | Notes |
|---|---|---|---|
| `ProgramId` (validated name) | `LoadedModule.name` / `ProgramSpace::module_by_name` | ✅ | Any gateway `ProgramId` is a valid module name (memory only requires non-empty; duplicates rejected). Natural lookup exists — no map needed. |
| `ExecutionId` (minted by `ExecutionSequence`) | none (memory is module-scoped) | ✅ new | Execution-Manager-level identity; must **not** be conflated with `ModuleId` (minted by `ProgramSpace`, never reused). |
| `CorrelationId` | none | ✅ new | Echo/verify inside the Execution Manager; mirrors the frozen backbone round-trip. |
| `ExecutionRequest::Load` | `ProgramSpace::load_module(&mut MemoryManager, &LoadedModule)` | ✅ | Requires an REI **source** (see §8 gap): `LoadedModule` needs REI bytes, and no compiler exists. |
| `ExecutionRequest::Run/Stop/Pause/Resume` | `ActiveSpace::call`/`close` (state only); no executor | ⚠️ partial | Lifecycle *state transitions* implementable; real execution semantics deferred (no Runtime/VM). |
| `ExecutionRequest::Inspect` | `ProgramSpace::module`/`module_by_name`/`read_rei`/`module_count` | ✅ | Summary string (matches `Inspected(String)` pattern). |
| `ExecutionLifecycle` (Loaded⇄Running⇄Paused→Completed/Stopped/Failed) | none (ActiveSpace depth is orthogonal) | ✅ new | Manager-owned mapping; memory has no execution-instance concept. |
| `ExecutionResult::Finished`/`ProgramOutcome` | none | ⏳ deferred | Requires a real run (Runtime/VM, Phase 7J.2+). |
| `ExecutionResult::Rejected` | `ra_memory::Error` (`UnknownModule`, `DuplicateModule`, …) | ✅ | Manager converts memory errors → `ExecutionFailure{code}`; no `From` impl (gateway stays dependency-free). |
| `GatewayState` (Idle⇄Executing→ShutDown) | `MemoryManager` lifecycle (new → shutdown) | ✅ | Manager mirrors the state gate; shutdown exactly-once. |
| `Gateway::shutdown` | `ProgramSpace::destroy` → `ActiveSpace::destroy` → `EntitySpace::destroy` → `MemoryManager::shutdown` | ✅ | Ordered teardown; see §6. |
| `FreezeSnapshot` (roadmap's "FreezeSnapshot → ProgramSpace") | none in ra-memory; lives in ra-persistence | ⚠️ gap | Snapshot carries **source text**, not REI. Not loadable without the compiler (Phase 7L). |

**Verdict:** The Phase 7J contract and the frozen memory architecture are **fundamentally compatible** — the memory crate was explicitly designed for exactly this consumer. Three gaps must be resolved by scope/decision, not by changing either crate: the REI source for `Load`, the composition/injection point, and the lifecycle/id mapping owned by the Execution Manager.

---

## 3. Audit findings (the 12 points)

### 3.1 Program loading representation
- Input: `LoadedModule<'a> { name: &'a str, rei: &'a [u8], constants: &'a [u8], code_map: &'a [CodeMapEntry] }` — transient buffers; Program Space **copies** them into manager-backed storage (empty payloads are legal, stored as a null-address marker).
- REI is an **opaque byte stream** whose length is tracked; the exact REI encoding is deliberately **open** (Program Space V1 §10). `CodeMapEntry { rei_offset: u32, source: SourcePos }` (8 bytes LE).
- `FreezeSnapshot` is **not** a loading representation: it is `.ra` source text + checksum. The frozen pipeline is `.ra → RA Core (lexer/parser/AST/IR) → REI → Program Space` — the lowering does not exist yet.

### 3.2 ProgramSpace creation/loading API
- `ProgramSpace::new(&mut MemoryManager) -> Result<ProgramSpace>` — registers `SpaceKind::Program`, allocates the module table.
- `load_module(&mut MemoryManager, &LoadedModule) -> Result<ModuleId>` — rejects empty names (`InvalidArgument`) and duplicate names (`DuplicateModule`).
- `unload_module(&mut MemoryManager, id)`, `destroy(self, &mut MemoryManager)` (reclaims all + unregisters the space).
- Reads (take `&MemoryManager`): `module(id) -> ModuleRecord`, `module_by_name(name) -> Option<ModuleId>`, `read_rei`, `read_constants`, `code_map_entry`, `code_map` iterator, `source_for_rei_offset`.
- Every operation passes the manager explicitly — the spaces are clients, they never own or borrow it.

### 3.3 Memory ownership rules (frozen)
- **MemoryManager is the sole owner of RA memory** (host regions, allocation metadata, space registry).
- **Runtime never allocates host memory directly**; **memory spaces never allocate host memory directly**; **all allocation flows through the manager**.
- **Runtime Loader owns the `MemoryManager` instance plus space creation and destruction** (manager.rs docs + frozen Execution Workflow).
- Spaces hold only bookkeeping (`SpaceId` + manager-backed structures); operations take `&mut MemoryManager`.
- `destroy()` is explicit (drop alone leaks — detectably); "Destroy Runtime Memory after execution" is a frozen rule.
- Consequence for 7J.1: the Execution Manager must **own** the `MemoryManager` and drive all space lifecycles; it never allocates outside it.

### 3.4 Logical address / reference types
- `LogicalAddress [region|slot|generation]` — `Copy`/`Hash`/`Eq`, validated on every use (`NotAllocated`, `StaleAddress`, `OutOfBounds`); never a raw pointer.
- RA-level handles: `SpaceId(u32)`, `ModuleId(u32)` (monotonic, never reused), `CellId`/`ScopeId` (Active Space), `EntityCellId` (Entity Grid), `ValueStorage` (embedded in `Value` for extended values).
- The **gateway must never expose any of these** (contract independence). The Execution Manager owns the mapping and never leaks addresses across the boundary.

### 3.5 FreezeSnapshot / snapshot APIs
- Location: **ra-persistence** (`FreezeSnapshot`), not ra-memory. `freeze(&LiveProgram)`, `source()`, `meta()`, `checksum()`, `verify_integrity()`, `frozen_at()`.
- `.raf` persistence path exists (`Pss::serialize_snapshot`/`deserialize_snapshot` in ra-syss).
- **Gap:** no `FreezeSnapshot → LoadedModule` bridge exists or can exist without the compiler (source text ≠ REI). The roadmap's "first `FreezeSnapshot → ProgramSpace` load path" must be rescoped for 7J.1 (see §7 risks, C2).

### 3.6 Shutdown/cleanup APIs
- `MemoryManager::shutdown(self) -> ShutdownReport`, `unregister_space`, `release_idle_regions`.
- Space teardown: `ProgramSpace::destroy`, `ActiveSpace::destroy`, `EntitySpace::destroy` (+ `destroy_value_list` before releasing cells), `GlobalEntityArea::destroy`, `ValueList::destroy`.
- Required order (7J.1's `Gateway::shutdown`): destroy all spaces/areas → `MemoryManager::shutdown` → gateway state `ShutDown` (terminal, exactly once).

### 3.7 Error boundaries
- `ra_memory::Error` (16 variants) + its own `Result`; deliberately **not bridged into ra-syss** (audit §18 note) and must not leak into ra-gateway (dependency-free).
- The Execution Manager owns the mapping: memory failure → `ExecutionResult::Rejected { reason: ExecutionFailure { code: LoadFailed | ExecutionFailed | Unsupported } }` (a **deterministic answer**, not a contract error); contract violations (unknown `ExecutionId`, wrong state, shutdown, correlation mismatch) → `Err(GatewayError)`.
- `DuplicateModule`/`UnknownModule` on Load → `Rejected { LoadFailed }`; `UnknownModule` on Inspect/Run of an unknown **execution** → `Err(GatewayError::UnknownExecution)` (execution-level, not module-level — two distinct checks).

### 3.8 Gateway `ProgramId` → memory model mapping
- Safe one-way mapping: gateway `ProgramId` (validated name: non-empty, ≤255 bytes, no `/` `\` NUL, not `.`/`..`, no trailing dot/space, not Windows-reserved) is always a **valid** `LoadedModule.name` (memory requires only non-empty; duplicates rejected).
- `ProgramSpace::module_by_name` is the natural `ProgramId → ModuleId` bridge — no host-side map required (aligns with the gateway's "no HashMaps" rule).
- **Do not conflate** the three `*Id` types: `ra_gateway::ProgramId` (name), `ra_persistence::ProgramId` (u64 instance id), `ra_memory::ModuleId` (minted). The Execution Manager is the only component that may hold the bridges.

### 3.9 Gateway `ExecutionRequest` variants implementable in 7J.1
| Variant | 7J.1 status | Implementation |
|---|---|---|
| `Load` | **Implementable** | `ReiProvider` seam → `LoadedModule` → `ProgramSpace::load_module` → mint `ExecutionId` → `Completed { state: Loaded }` |
| `Inspect` | **Implementable** | `ProgramSpace`/manager queries → `Inspected { summary }` |
| `Stop` | **Implementable** | lifecycle → `Stopped` (state-level; no real execution to stop yet) |
| `Run` / `Pause` / `Resume` | **State transitions only** | `ActiveSpace::call`/`close` + lifecycle table can drive the *states*; **real execution semantics deferred** |
| `shutdown()` | **Implementable** | ordered space/manager teardown → `ShutDown` |

### 3.10 Variants that must remain deferred
- **Real `Run`** (REI execution loop), **`Pause`/`Resume`** of a genuinely running program, **`ExecutionResult::Finished`/`ProgramOutcome`** — all need the Runtime/VM (Phase 7J.2+).
- **Compiler-produced REI** (the real `ReiProvider`) — Phase 7L.
- `.rab`/`.raf`/`.rap` byte encodings, async execution, threading, networking — out of scope by frozen design (synchronous, deterministic).

### 3.11 Conflicts between Phase 7J and the frozen memory architecture
**No fundamental conflict** — memory is frozen and waiting for this exact consumer. Five non-blocking items must be decided/documented:

- **C1 — Composition/injection point (the big one).** `ra-syss` must never depend on `ra-runtime` (rule 3); `software` and `ra-bootstrap` must never depend on `ra-runtime` (rules 2/4). So *nothing in the current graph may construct the Execution Manager*. Required decision: rank `ra-runtime` at **2** (sibling of SySS; it must consume memory/gateway/persistence, all rank 1 — rank 1 is impossible for it by the strictly-decreasing rule), and inject the gateway into SySS through an **additive constructor** (`SySS::initialize_with_gateway(Box<dyn Gateway>)`, mirroring the 7G.1 `with_storage_root` pattern) called by the **future application shell** (Frontend/IDE), not by Bootstrap/software. The shell's forbidden-table entry is the intended friction point to revise when the shell lands.
- **C2 — FreezeSnapshot→REI gap.** The roadmap's "first `FreezeSnapshot → ProgramSpace` load path" is **not end-to-end implementable**: the snapshot is source text, Program Space needs REI, and there is no compiler. 7J.1 must introduce the `ReiProvider` seam and scope to "provider → ProgramSpace load path"; the real provider is the compiler.
- **C3 — Four identity spaces.** `ra_gateway::ProgramId` (name), `ra_persistence::ProgramId` (u64), `ra_memory::ModuleId` (minted), `ra_gateway::ExecutionId` (minted). The name `ProgramId` exists in two crates — never conflate; the Execution Manager bridges via names/`module_by_name`.
- **C4 — Lifecycle mapping is manager-owned.** Memory has no execution-instance concept and no lifecycle type; `ExecutionId` + `ExecutionLifecycle` are Execution-Manager state, mapped onto `ProgramSpace` records and the `ActiveSpace` chain. This is a new type (`ExecutionRecord`), not a memory change.
- **C5 — Hub expansion.** The Phase 7J description mentions "Execution/DB hub expansion points". Attaching the gateway **behind the backbone** (architecture.md) via additive injection is the recommended path; adding an **Execution hub** to the frozen hub graph would touch the frozen kernel/registry/graph and is **not recommended** for 7J.1.

### 3.12 Exact dependency direction required
```
ra-gateway        → (none)                  [frozen, dependency-free]
ra-memory         → ra-common               [frozen, leaf]
ra-persistence    → ra-common               [frozen, leaf]
ra-runtime  (new) → ra-gateway, ra-memory, ra-persistence, ra-common   [rank 2 — sibling of ra-syss]
ra-syss           → ra-gateway, ra-persistence   [unchanged; trait call only, NEVER ra-runtime]
ra-bootstrap      → ra-syss                [unchanged]
software          → ra-bootstrap           [unchanged]
future shell      → software/syss + ra-runtime   [the composition root; revises the shell's forbidden table deliberately]
```
No crate may depend on `ra-runtime` except the future application shell. `ra-syss → ra-gateway` already passes the guard (gateway=1, syss=2).

---

## 4. Required Execution Manager types (new crate `ra-runtime`)

| Type | Role |
|---|---|
| `ExecutionManager` | Implements `ra_gateway::Gateway`. Owns `MemoryManager`, `ProgramSpace`, `ActiveSpace`, `EntitySpace`, `GlobalEntityArea`; the `ExecutionSequence`-minted `ExecutionId`s; and the internal `ExecutionRecord` table (`ExecutionId → { ProgramId, ModuleId, ExecutionLifecycle, ActiveSpace depth }`). |
| `ExecutionManagerConfig` | Construction config (mirrors `MemoryManagerConfig` style). |
| `ReiProvider` trait | `fn module(&self, program: &ProgramId) -> GatewayResult<LoadedModule>` — the REI source seam. Real impl = compiler (Phase 7L); 7J.1 ships a test/host impl over pre-lowered bytes. |
| `ExecutionRecord` (internal) | The manager-owned lifecycle/id mapping (§3.11 C4). |
| `ExecutionError` + mapping | `From<ra_memory::Error>`; converter → `ExecutionFailure { FailureCode }` for `ExecutionResult::Rejected`. |
| Ordered teardown | `destroy()`: spaces/areas → `MemoryManager::shutdown` → gateway `ShutDown` (exactly once). |
| Gate behavior | Mirrors the Phase 7J test double: `Idle → Executing → Idle` per synchronous call, `ShutDown` terminal, `UnknownExecution` rejection, correlation echo/`verify_answers`. |

## 5. Required Runtime foundation types (defined in 7J.1, semantics later)

| Type | Role |
|---|---|
| `RuntimeLoader` | Per the frozen docs, the **only component that populates runtime memory** and owns the `MemoryManager` instance + space creation/destruction. 7J.1's Program Space load path is its first responsibility. |
| `Program` | A loaded-program handle (ModuleId + entry REI offset + scope table) derived from `ProgramSpace` records. |
| `Frame` / `ExecutionContext` | Active Space `ActiveRecord` (ScopeId + REI position) + REI local/global scope state (Active Space §8). |
| `Vm` / `Executor` (shape only) | Deferred execution engine (Phase 7J.2+). `Rei` stays an opaque byte stream (encoding open). |

## 6. Exact files that would need modification (7J.1 implementation)

| File | Change |
|---|---|
| `software/runtime/Cargo.toml` (+ `src/lib.rs`, `execution_manager.rs`, `runtime_loader.rs`, `error.rs`, `rei_provider.rs`) | **New crate.** Depends on `ra-gateway`, `ra-memory`, `ra-persistence`, `ra-common`. |
| `Cargo.toml` (workspace root) | Add `"software/runtime"` to `members`. |
| `Cargo.lock` | Regenerated. |
| `scripts/check-architecture.sh` | `RANK[ra-runtime]=2`; `FORBIDDEN[ra-runtime]` (never → ra-syss/ra-bootstrap/software/frontend/ide/database); `ra-syss`'s existing forbidden entry already lists `ra-runtime`. |
| `software/syss/src/platform.rs` (+ `platform_interface.rs`) | **Additive only:** `SySS::initialize_with_gateway(Box<dyn Gateway>)` (+ `PlatformInterface` counterpart), frozen signatures intact; execution-control ops may route through the stored gateway (no shape change). |
| `docs/architecture.md` | Phase 7J.1 section (rank, injection, scope, id mapping). |
| **Not touched (frozen)** | `ra-gateway`, `ra-memory`, `ra-persistence`, `ra-common`, the hub graph/backbone contracts, `PlatformInterface` shape, storage/lifecycle implementation. |

**Integration testing note:** `ra-runtime` proves `Gateway → ExecutionManager → ProgramSpace` in its own tests (full load/read/destroy round-trip, `0 live allocations` at shutdown). `ra-syss` tests can inject a **mock** `Gateway` (trait from `ra-gateway`, which ra-syss already depends on) to prove the additive constructor — **without** depending on `ra-runtime` (a `[dev-dependencies]` edge would be caught by the guard). The real gateway is wired into SySS only by the future shell.

## 7. Risks / contract conflicts (summary)

1. **Composition root undefined** (C1) — nothing may currently construct the Execution Manager; requires the rank-2 + additive-injection + future-shell decision. Highest-priority item; a doc/guard decision, not a code blocker.
2. **FreezeSnapshot ≠ REI** (C2) — the roadmap's headline 7J.1 artifact must be rescoped to an REI-provider load path.
3. **Identity conflation risk** (C3) — `ProgramId` in two crates; `ModuleId` vs `ExecutionId`; enforce via the manager-only bridging rule.
4. **Rank revision is mandatory** — `ra-runtime` cannot be rank 1 (needs rank-1 deps) and cannot be rank 3+ (nothing could feed it memory); rank 2 with a shell composition root is the only acyclic shape.
5. **No hub expansion** — do not add an Execution hub to the frozen hub graph in 7J.1; attach behind the backbone by injection.
6. **Lifecycle mapping** (C4) — new manager-owned `ExecutionRecord`; explicit mapping gateway-lifecycle ↔ memory state; never invent memory-side lifecycle.
7. **Destroy ordering** (C6) — exactly-once ordered teardown; `ProgramSpace.destroy`/`ActiveSpace.destroy`/`EntitySpace.destroy` before `MemoryManager::shutdown`; leaks are detectable (`ShutdownReport`).

## 8. Recommended Phase 7J.1 implementation order

0. **Freeze the decisions** (doc + guard change only): `ra-runtime` at rank 2; additive `SySS::initialize_with_gateway`; shell as composition root; 7J.1 scope = REI-provider load path (not snapshot→REI).
1. Scaffold `ra-runtime`; `ExecutionManager` skeleton implementing `Gateway` (state gate, mints, correlation, `ExecutionRecord`).
2. `RuntimeLoader` foundation: `MemoryManager` + `ProgramSpace` (+ `ActiveSpace`/`EntitySpace` creation) and the ordered destroy path.
3. `ReiProvider` seam; implement **Load** (`Completed { Loaded }`).
4. Implement **Inspect** and **Stop**; Run/Pause/Resume as lifecycle-state transitions only.
5. Error mapping (memory `Error` → `ExecutionFailure`; `DuplicateModule` → `Rejected { LoadFailed }`).
6. `shutdown()` exactly-once; `ShutdownReport`-verified teardown.
7. Integration proof: ra-runtime tests (load test REI → read back → destroy → 0 live allocations); ra-syss additive constructor + mock-gateway tests.
8. Docs + full verification suite.

## 9. Verification plan

- `cargo fmt --all --check`
- `cargo check --workspace`
- `cargo clippy --workspace --all-targets`
- `cargo test --workspace` (new: gateway-contract compliance, Program Space round-trip, lifecycle table, teardown `live_allocations() == 0`, correlation safety, deterministic re-runs)
- `cargo tree --workspace` (must show `ra-runtime → {ra-gateway, ra-memory, ra-persistence, ra-common}`, no cycle)
- `bash ./scripts/check-architecture.sh` (updated tables; must pass)
- `cargo run -p software` (unchanged boot/shutdown smoke; gateway not yet wired in the binary)

## 10. Recommendation

**GO** for Phase 7J.1 implementation, subject to two prerequisite decisions and one explicit non-goal:

- **Prerequisite 1 (composition):** freeze `ra-runtime` at rank 2, the additive `SySS::initialize_with_gateway` injection, and the future application shell as the composition root. No `ra-syss → ra-runtime` edge, ever.
- **Prerequisite 2 (scope):** 7J.1 delivers the **REI-provider → ProgramSpace load path** and the Execution Manager skeleton (Load / Inspect / Stop / lifecycle-state transitions / ordered shutdown). The `FreezeSnapshot → ProgramSpace` artifact is deferred until the compiler exists (Phase 7L); 7J.1 proves the path with pre-lowered test REI.
- **Explicit non-goals:** no REI execution, no VM, no compiler, no async/threads/networking, no changes to `ra-gateway` or `ra-memory`.

The frozen memory architecture and the Phase 7J contract are compatible as-is; nothing requires changing either crate. The remaining work is new-manager code, one additive SySS constructor, and the deliberate layer-table/rank decision.
