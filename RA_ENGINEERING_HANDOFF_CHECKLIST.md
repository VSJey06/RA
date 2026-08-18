# RA Engineering Handoff & Continuity Checklist

**Baseline:** 2026-08-14  
**Current milestone:** RA-RUST-4 — Platform Boot Integration

## Purpose

Use this file at every session handoff to prevent architectural drift and keep implementation, tests, documentation, ownership, and frozen boundaries synchronized.

---

## 1. Architectural North Star

### SySS
SySS controls the RA software/application platform:

- startup and platform lifecycle
- platform services
- workspace/project/package/document management
- persistence boundary
- settings/history/log
- storage
- PlatformInterface
- frontend-facing platform state

### RA Core
RA Core controls the RA language and execution system:

- language
- compiler
- execution manager
- runtime
- VM
- bytecode execution
- RA Core memory integration
- language/runtime libraries

### Required boundary

```text
Windows / OS
    ↓
software.exe
    ↓
Bootstrap
    ↓
PlatformInterface
    ↓
SySS
    ↓
RA Core Gateway
    ↓
RA Core
    ├── Compiler
    ├── Execution Manager
    ├── Runtime / VM
    └── Memory
```

**Rules**

- SySS and RA Core remain separate products inside one application.
- SySS must not absorb compiler/runtime/VM responsibilities.
- RA Core must not absorb application/platform responsibilities.
- RA Core Gateway is the controlled bridge between them.

---

## 2. Completed Foundation

### Workspace / repository

- [x] Rust workspace
- [x] `ra-common`
- [x] `ra-memory`
- [x] `ra-persistence`
- [x] `ra-syss`
- [x] `ra-bootstrap`
- [x] `software`
- [x] Dependency direction
- [x] Architecture guard
- [x] No known dependency cycle

### RA Memory

- [x] Program Space
- [x] Active Space
- [x] Entity Space
- [x] Value List
- [x] Registry Space foundation
- [x] Memory tests
- [x] Memory ownership separated from SySS

### SySS

- [x] Platform Interface
- [x] Platform State
- [x] Hub IDs/domains
- [x] Hub lifecycle
- [x] Registry
- [x] Hub graph/routing contracts
- [x] Hub authorities
- [x] Platform kernel
- [x] Built-in authorities
- [x] Platform Backbone
- [x] Backbone runtime
- [x] Request/Response
- [x] Correlation ID
- [x] Platform lifecycle
- [x] Safe shutdown
- [x] Platform services
- [x] Active Objects
- [x] Workspace persistence
- [x] Project persistence
- [x] Package persistence
- [x] Document persistence
- [x] Storage root
- [x] PSS integration
- [x] Recovery integration
- [x] Settings persistence
- [x] History persistence
- [x] Log persistence
- [x] Theme/View platform state

### Frozen boundaries

- [x] Platform Kernel ownership
- [x] Backbone ownership
- [x] Authority ownership
- [x] Storage ownership
- [x] Request → Backbone → Authority → Service → Response
- [x] SySS / RA Core separation
- [x] `ra-memory` ownership boundary

---

# 3. CURRENT ACTIVE MILESTONE

## RA-RUST-4 — Platform Boot Integration

### Objective

```text
software.exe
    ↓
Bootstrap
    ↓
PlatformInterface
    ↓
SySS
    ↓
Platform Ready
```

### Entry point

- [ ] `software` actually invokes Bootstrap
- [ ] No demo/placeholder entry behavior
- [ ] No `software` → lower-level platform bypass
- [ ] Entry dependency boundaries preserved

### Bootstrap

- [ ] Real startup sequence
- [ ] Bootstrap invokes PlatformInterface
- [ ] Bootstrap remains orchestration-only
- [ ] Startup errors propagate
- [ ] Shutdown errors propagate
- [ ] No duplicated SySS startup logic

### PlatformInterface

- [ ] Bootstrap reaches SySS only through PlatformInterface
- [ ] No Bootstrap → SySS bypass
- [ ] Startup contract is real
- [ ] Shutdown contract is real

### SySS startup

- [ ] Platform state initialized
- [ ] Kernel initialized
- [ ] Required authorities available
- [ ] Required services available
- [ ] Storage initialized according to existing architecture
- [ ] Startup recovery runs according to existing architecture
- [ ] Platform reaches Running/Ready

### Runtime

- [ ] `cargo run -p software` executes the real boot chain
- [ ] Process remains alive where required
- [ ] Clean shutdown works
- [ ] Double shutdown prevented
- [ ] Startup failure is deterministic

### Verification

- [ ] `cargo fmt --all --check`
- [ ] `cargo check --workspace`
- [ ] `cargo clippy --workspace --all-targets`
- [ ] `cargo test --workspace`
- [ ] `cargo tree --workspace`
- [ ] `scripts/check-architecture.sh`
- [ ] `cargo run -p software`

### Completion gate

RA-RUST-4 is complete only when:

- [ ] executable boot path is real
- [ ] canonical ownership path is preserved
- [ ] startup/shutdown tests pass
- [ ] architecture guard passes
- [ ] no forbidden dependency introduced
- [ ] no frozen subsystem redesigned
- [ ] completion report recorded

---

# 4. NEXT — TERMINAL

Do not begin until RA-RUST-4 is complete.

- [ ] Terminal surface
- [ ] Command input
- [ ] Command dispatch
- [ ] Output handling
- [ ] `exit`
- [ ] Error display
- [ ] Clean shutdown
- [ ] Terminal → PlatformInterface
- [ ] No Terminal → SySS bypass
- [ ] Terminal integration tests

---

# 5. RA CORE GATEWAY

Do not implement Compiler/Runtime/VM before the Gateway contract is frozen.

- [ ] Read authoritative Gateway documents
- [ ] Inspect SySS boundary
- [ ] Inspect RA Core architecture
- [ ] Inspect `ra-memory`
- [ ] Define Gateway ownership
- [ ] Define operations
- [ ] Define request/result model
- [ ] Define error boundary
- [ ] Define lifecycle boundary
- [ ] Define compile boundary
- [ ] Define execution boundary
- [ ] Define stop/pause/resume boundary if required
- [ ] Define memory interaction boundary
- [ ] Add tests
- [ ] Freeze Gateway contract

**Not part of Gateway contract phase:**

- [ ] Compiler implementation
- [ ] Runtime implementation
- [ ] VM implementation
- [ ] Execution Manager implementation
- [ ] Full RA Core implementation

---

# 6. RA CORE IMPLEMENTATION ROADMAP

## Language / Compiler

- [ ] `.ra` source handling
- [ ] Lexer
- [ ] Parser
- [ ] AST
- [ ] Semantic processing
- [ ] Constant Pool
- [ ] Compiler
- [ ] Bytecode generation
- [ ] `.rab` support when codec specification is implemented

## Execution

- [ ] Execution Manager
- [ ] Runtime Loader
- [ ] Runtime
- [ ] VM
- [ ] Execution Context
- [ ] Program Space integration
- [ ] Active Space integration
- [ ] Entity Space integration
- [ ] Registry Space integration
- [ ] `ra-memory` integration

## Libraries

- [ ] Core Library
- [ ] Standard Library
- [ ] DB Library
- [ ] Built-in system
- [ ] Runtime/library bridge

---

# 7. FRONTEND / IDE

Do not let frontend redefine backend ownership.

- [ ] Frontend shell
- [ ] Boot/loading animation
- [ ] Terminal page
- [ ] IDE workspace
- [ ] Editor
- [ ] Workspace/project UI
- [ ] Package UI
- [ ] Settings UI
- [ ] History UI
- [ ] Log UI
- [ ] Debugger
- [ ] Database UI
- [ ] Theme rendering
- [ ] View rendering
- [ ] Frontend → PlatformInterface only
- [ ] RA Core reached through Gateway

---

# 8. DO NOT IMPLEMENT PREMATURELY

- [ ] Compiler before Gateway
- [ ] Runtime before Gateway
- [ ] VM before Gateway
- [ ] Direct SySS → VM communication
- [ ] Direct Frontend → RA Core communication
- [ ] PlatformInterface → filesystem bypass
- [ ] Service → Service bypass
- [ ] Authority → Authority bypass
- [ ] Second storage engine
- [ ] Second messaging system
- [ ] Second memory system
- [ ] Duplicate persistence system
- [ ] Duplicate recovery system
- [ ] Binary formats before authoritative codec specification

---

# 9. SESSION HANDOFF RECORD

## Phase

`____________________________`

## Date

`____________________________`

## Objective

`____________________________`

## Completed

- [ ] Implementation
- [ ] Tests
- [ ] Documentation
- [ ] Architecture verification
- [ ] Runtime verification

## Modified files

```text
<exact paths>
```

## Verification

```text
cargo fmt:
cargo check:
cargo clippy:
cargo test:
cargo tree:
architecture guard:
cargo run:
```

## New dependencies

```text
None / list:
```

## Architectural changes

```text
None / list:
```

## Frozen components touched

```text
None / list + justification:
```

## Known gaps

```text
<exact gaps>
```

## Intentionally deferred

```text
<exact deferred work>
```

## Next phase

```text
<exact next phase>
```

---

# 10. ARCHITECTURE DRIFT CHECK

Before accepting any change:

- [ ] New owner for an existing responsibility?
- [ ] PlatformInterface bypass?
- [ ] Backbone bypass?
- [ ] Authority bypass?
- [ ] Second registry?
- [ ] Second persistence mechanism?
- [ ] Second memory mechanism?
- [ ] Filesystem logic in wrong layer?
- [ ] Kernel internals exposed?
- [ ] SySS coupled directly to RA Core internals?
- [ ] RA Core coupled directly to Frontend?
- [ ] Frozen contract changed?
- [ ] Conflict with authoritative specification?

If any answer is **YES**:

**STOP → AUDIT → RESOLVE → IMPLEMENT.**

---

# 11. DOCUMENT AUTHORITY

When documents disagree, do not silently choose.

Use:

1. Master Architecture Constitution
2. Subsystem-specific frozen specifications
3. Architecture decisions / phase specifications
4. Current live repository architecture
5. Phase implementation reports
6. General assumptions

Record conflicts explicitly.

---

# 12. DEFINITION OF COMPLETE

A phase is NOT complete because code exists or compilation succeeds.

A phase is complete only when:

```text
Implementation
      +
Tests
      +
Architecture
      +
Ownership
      +
Security
      +
Runtime verification
      +
Documentation
      +
Handoff record
      =
COMPLETE
```

---

# 13. CURRENT TRACK

```text
FOUNDATION
    |
    +-- Workspace                         [x]
    +-- Memory                            [x]
    +-- Persistence                       [x]
    +-- SySS                              [x]
    +-- Platform Kernel                   [x]
    +-- Backbone                          [x]
    +-- Platform Services                 [x]
    +-- Active Objects                    [x]
    +-- Persistence integration           [x]
    +-- Settings/History/Log              [x]
    |
    v
RA-RUST-4 BOOT INTEGRATION               [ACTIVE]
    |
    v
TERMINAL                               [PENDING]
    |
    v
RA CORE GATEWAY                         [PENDING]
    |
    v
RA CORE COMPILER                        [PENDING]
    |
    v
RA CORE RUNTIME / VM                   [PENDING]
    |
    v
RA CORE LIBRARIES                      [PENDING]
    |
    v
FRONTEND / IDE                         [PENDING]
    |
    v
PRODUCTION HARDENING                   [PENDING]
```

---

# 14. CURRENT HANDOFF

**Current phase:** RA-RUST-4 — Platform Boot Integration

**Immediate target:**

```text
software.exe
    ↓
Bootstrap
    ↓
PlatformInterface
    ↓
SySS
    ↓
RA PLATFORM READY
```

Do not start Terminal, RA Core Gateway, Compiler, Runtime, VM, or Frontend until the current phase completion gate is satisfied.

**Next action:** audit the current entry point, Bootstrap, PlatformInterface, and SySS startup implementation, then make the smallest changes required to establish the canonical executable boot path.
