# RA Software Platform â€” Dependency Architecture

Frozen layer rules for the Cargo workspace. These rules are **enforced
automatically** by `scripts/check-architecture.sh` (CI-ready: run
`bash scripts/check-architecture.sh` from the workspace root).

## Layer model

```
       â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
       â”‚  software (entry binary)     â”‚   future Frontend / Bootstrap entry
       â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                       â”‚
       â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
       â”‚  ra-bootstrap                â”‚   starts / stops the platform
       â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                       â”‚
       â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
       â”‚  ra-syss                     â”‚   the platform backbone (Phase 7D hub graph)
       â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                       â”‚
        â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
        â”‚  ra-persistence             â”‚   codec layer, artifact model, LPM
        â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                       â”‚
       â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–¼â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
       â”‚  ra-common                   â”‚   shared foundation, zero dependencies
       â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜

  ra-memory (Memory Manager) is a leaf above ra-common only,
  parallel to ra-persistence.
```

Arrows point **downward** (dependency direction). Every layer may depend only
on crates strictly below it, so the graph is always acyclic.

## Rules

| # | Rule |
|---|------|
| 1 | Every layer depends only on crates strictly below it (acyclic downward flow). |
| 2 | The `software` binary (future Frontend / Bootstrap entry) must **never** directly depend on `ra-persistence`, `ra-memory`, `ra-runtime` or `ra-base`. |
| 3 | `ra-syss` must **never** depend on `ra-frontend`, `ra-ide`, `ra-runtime` or `ra-base` (nor on `ra-bootstrap`, `ra-memory`, `ra-database`). |
| 4 | `ra-bootstrap` reaches lower layers **exclusively** through `ra-syss`. |
| 5 | `ra-persistence` and `ra-memory` are leaves above `ra-common` only. |
| 6 | `ra-common` has zero dependencies. |

Rules 2 and 3 are the hard contractual boundaries of the frozen architecture:
storage, memory and execution layers are never reachable from the UI/entry
layer, and the platform backbone never reaches into the outer application
layers.

## Current dependency graph (boot chain)

```
software          â†’ ra-bootstrap
ra-bootstrap      â†’ ra-syss
ra-syss           â†’ ra-persistence
ra-syss           â†’ ra-gateway
ra-persistence    â†’ ra-common
ra-memory         â†’ ra-common
ra-gateway        â†’ (none)
ra-memory-gateway â†’ ra-common
ra-runtime        â†’ ra-gateway
ra-runtime        â†’ ra-memory-gateway
ra-runtime        â†’ ra-common
ra-memory-gateway-adapter â†’ ra-memory-gateway
ra-memory-gateway-adapter â†’ ra-memory
ra-memory-gateway-adapter â†’ ra-common
ra-common         â†’ (none)
```

`ra-gateway` (Phase 7J) is the dependency-free RA Core Gateway contract;
`ra-runtime` (Phase 7J.1) is the RA Core side of that contract, a rank-2
sibling of `ra-syss`. The two meet only through the gateway contract at the
future composition root â€” `ra-syss` never depends on `ra-runtime` (see *RA
Core Gateway & Runtime foundation* below).

The **Execution â†” Memory Gateway** (`ra-memory-gateway`, rank 1) is the
dependency-free contract between the Execution compartment and Memory â€”
exactly six operations (`initialize`, `load_module`, `module_by_name`,
`module`, `teardown`, `live_allocations`) â€” and the **Memory Adapter**
(`ra-memory-gateway-adapter`, rank 2) implements it over the existing
`ra-memory`. `ra-runtime` (rank 2) depends on the contract crate only and
receives the adapter injected as `Box<dyn MemoryGateway>` from the
composition root; the two rank-2 crates never depend on each other, and
`ra-runtime` no longer depends on `ra-memory` directly (see *RA Core
Gateway & Runtime foundation* below).

The `software` entry binary now depends on `ra-bootstrap` (the executable
startup path is finalized in Phase 7D):

```
main() â†’ Bootstrap::start() â†’ PlatformInterface::start() â†’ SySS::initialize()
        â†’ Platform Kernel Initialization â†’ Platform Ready
```

Bootstrap reaches the platform **exclusively** through
`ra_syss::PlatformInterface` â€” it never calls SySS or any lower layer
directly. `PlatformInterface::start` is the single public platform entry
point; it initializes the SySS platform skeleton behind the interface.

`SySS::initialize()` runs the **Platform Kernel Initialization** (Phase
7D.3): it creates the built-in hub authorities (workspace, project, package,
settings, history, log, storage, device), registers them with the hub
registry, runs the startup lifecycle transitions
(`Registered â†’ Initialized â†’ Active`), attaches the **Platform Backbone**
communication contracts (Phase 7E), brings the **backbone runtime** online
(Phase 7E.1 â€” deterministic synchronous delivery through the authority
delivery boundary) and verifies kernel readiness before the platform is
**Ready**. This is startup orchestration only â€” Phase 7F.1 lands the common
Service abstraction and the Log proof service behind the authorities; full
domain services, active objects and payload processing arrive later.

## Platform Backbone (Phase 7E)

The **Platform Backbone** is the communication infrastructure of the RA
Software Platform. Architecturally the subsystem is the Platform Backbone;
its implementation is the **Message Backbone** (the earlier phase name is
preserved in prose throughout the codebase).

The backbone is the **single communication path** of the platform. No layer
may bypass it:

```
Frontend
   â†“
PlatformInterface
   â†“
Platform Backbone
   â†“
Authority
   â†“
Service
   â†“
RA Core Gateway (future)
   â†“
RA Core
```

It transports **commands, requests, responses, events, notifications,
lifecycle signals and platform broadcasts** between the platform hubs.

Phase 7E creates the communication **contracts only** (the `backbone` module
of `ra-syss`): the seven-kind message vocabulary, the message envelope and
the backbone interface (`accept`, `route`, `dispatch`, `reply`,
`broadcast`). The backbone is the **first consumer** of the Platform
Kernel's registry, hub graph, routing contracts and authorities, and its
attachment is part of kernel readiness. Each backbone operation enforces its
kind contract: only broadcasts and platform lifecycle signals travel
platform-wide, and only responses travel as replies.

### Platform Backbone runtime (Phase 7E.1)

Phase 7E.1 turns the contracts into the **minimum real communication path**
â€” a deterministic synchronous runtime (no async, no queueing, no network
transport, no persistence of messages):

```
PlatformInterface
   â†“  (backbone message)
Platform Backbone    accept â†’ validate â†’ resolve target â†’ deliver â†’ return result
   â†“  (target resolution: exists Â· registered Â· authority present Â· Active)
Target Authority     (delivery boundary â†’ delivery receipt)
```

* **Target resolution** reuses the existing contracts only â€” the `Registry`,
  the `HubGraph`, the `Router`/`HubRoute` and the hub authorities. There is
  no second registry and no second routing system.
* **Delivery** reaches the authority through its controlled delivery boundary
  (`HubAuthority::receive`); inactive authorities never receive platform
  messages. The authority acknowledges receipt with a **delivery receipt**
  (`accepted` / `delivered`; rejection returns the existing Hub error).
* **Payloads** stay domain-neutral and empty â€” no workspace, project, storage
  or compiler payload types, no serialization, no `ra-persistence` coupling.
* **PlatformInterface** wires a single proof operation (`probe`) through the
  backbone; every other platform operation remains a contract.

### Authority â†’ Service (Phase 7F.1)

Phase 7F.1 establishes the **service architecture** on top of the frozen
backbone and kernel: the common, domain-neutral **Service abstraction** owned
by each SySS Authority, plus exactly **one minimal proof service**.

```
PlatformInterface
   â†“  (backbone message)
Platform Backbone      (transport Â· target resolution Â· delivery receipt)
   â†“
Target Authority       (domain ownership Â· forwards to its owned service)
   â†“  (service invocation)
Service                (domain work Â· the Log proof service)
   â†“
ServiceResult          (service execution result)
```

Layer responsibilities:

* **Backbone** = communication / delivery. Its `DeliveryReceipt` is the
  message **transport / delivery** result.
* **Authority** = domain ownership. It owns its domain's
  `State â†’ Services â†’ Events â†’ Policies`; **services never own
  authorities**.
* **Service** = domain work. Its `ServiceResult` is the **service execution
  result** â€” distinct from the delivery receipt. Phase 7F.1 vocabulary:
  `accepted` / `completed` / `rejected`, with no business payloads yet.

The **LogService** is the Phase 7F.1 proof service, owned by the Log
Authority. It performs only a minimal deterministic operation â€” accepting a
platform log request and returning a `ServiceResult`. It is **not** a
logging subsystem, and it stays the proof service during Phase 7F.2.

Lifecycle relationship: a service must not become reachable before its
owning authority is `Active`
(`Authority Registered â†’ Initialized â†’ Active â†’ Service Ready`); the
authority invocation boundary enforces this. Invocation goes through the
authority's controlled delivery boundary â€” the backbone is never bypassed.

### Platform Services (Phase 7F.2)

Phase 7F.2 populates the service foundation with the **seven domain
services**, one per domain, each bound to its owning authority by
composition (no second registry â€” the hub `Registry` registers
hubs/authorities; service binding is the authority-ownership model itself):

| Service | Owned by | Minimal domain behavior |
|---------|----------|--------------------------|
| WorkspaceService | Workspace Authority | inspect / accept workspace operations |
| ProjectService | Project Authority | inspect / accept project operations |
| PackageService | Package Authority | inspect / accept package operations |
| SettingsService | Settings Authority | inspect / accept settings operations |
| HistoryService | History Authority | inspect / accept history operations |
| StorageService | Storage Authority | platform-storage proof operation only |
| DeviceService | Device Authority | device capability probe only |
| LogService | Log Authority | Phase 7F.1 proof service (preserved) |

Every domain service performs only **minimal deterministic domain
operations** through a shared operation/kind contract: a `Command` carrying
`Accept` completes a minimal domain operation; a `Request` carrying
`Inspect` completes an inspection of the (minimal) domain state; a
`Notification` is accepted; mismatched kind/operation pairs and
non-request kinds are rejected (`ServiceResult::Rejected`). The operation
is the minimal domain-neutral payload (`ServiceOperation`, carried by
`BackbonePayload::Operation`) â€” no serialization, no `ra-persistence`
coupling, no compiler/runtime/memory payloads.

**Storage boundary** â€” `StorageService` is a platform service only: it
completes a minimal platform-storage proof operation and does **not**
absorb persistence implementation. The boundary stays
`StorageAuthority â†’ StorageService â†’ future FSS / PSS / Recovery
integration`; the `ra-persistence` codec architecture, PSS and Recovery are
untouched.

**Device boundary** â€” `DeviceService` is a platform boundary only: its
inspection is a deterministic capability/probe operation. No drivers, no
hardware communication, no networking, no USB, no filesystem device
drivers and no OS kernel calls.

**PlatformInterface** wires the minimum operations to prove the services:
the workspace, project, package, settings, history and log accessors travel
the backbone to their authorities and services; `theme` and `view` remain
contracts (settings UI state, not services). The frozen interface shape is
preserved â€” it has no `storage()`/`device()` accessor yet, so the Storage
and Device services are proven internally (a genuine gap for a later
phase).

### Real per-domain behavior (Phase 7F.3)

Phase 7F.3 converts the Phase 7F.2 proof-only services into the first real
domain-state services. Each service owns a **private domain state** (kept
private; controlled operations only) and performs **minimal real domain
operations**:

| Service | Domain state | Real operations |
|---------|--------------|-----------------|
| WorkspaceService | the real Workspace + Document active objects (persisted since 7H.1/7H) | Open, Close, Inspect; document ops |
| ProjectService | the real Project active object (persisted since 7H.1) | Open, OpenIn, Close, Inspect |
| PackageService | the real Package active object (persisted since 7H.1) | Open, OpenIn, Close, Inspect |
| SettingsService | persisted key/value settings (7H.2) | Set, Get, Inspect |
| HistoryService | persisted operation entries (7H.2) | Record, Clear, Inspect |
| LogService | persisted structured log records (7H.2; 7F.1 proof behavior preserved) | Record, RecordLog, Clear, Inspect |
| StorageService | platform-storage boundary capability | Probe, Inspect; Save/Load/Recover (7G.1) |
| DeviceService | platform device capability | Probe, Inspect |

State is mutated through the single service invocation boundary only; no
service holds a reference to another service or to the backbone, so one
service can never mutate another's state (state isolation). The operations
travel as explicit domain-neutral payloads (`BackbonePayload::Operation`
carrying `Open`/`Close`/`Set`/`Record`/`Clear`/`Probe`/`Inspect`/`Accept`) â€”
no untyped maps, no serialization, no `ra-persistence` coupling. Because the
payloads own their arguments, the message envelope is no longer `Copy`:
messages move through the backbone and are cloned when read again.

**Request â†’ Response path** â€” a `Request` carrying `Inspect` is answered
with `ServiceResult::Inspected(summary)` â€” a deterministic summary of the
domain state. Phase 7F.4 completes the round-trip (next section): the
summary is converted into an explicit `Response` message delivered back over
the backbone to the caller.

**PlatformInterface** â€” the six wired accessors (workspace, project, package,
settings, history, log) inspect the real domain state of their services
through the backbone; `theme` and `view` are real settings-backed
platform-state operations since Phase 7H.2 (with additive
`get_theme`/`set_theme`/`get_view`/`set_view`); Storage and Device remain
proven internally (the frozen interface has no accessors for them yet). The
interface shape is preserved.

**Storage and Device boundaries** â€” unchanged: `StorageAuthority â†’
StorageService â†’ future FSS / PSS / Recovery integration`, and the Device
service as a platform abstraction only (no drivers, no I/O).
`ra-persistence`, PSS and Recovery are untouched.

Later phases add the device connector, the RA Core Gateway and the
Frontend â€” never bypassing the backbone. (Active objects landed in 7H,
active-object persistence in 7H.1, settings/history/log persistence and the
theme/view foundation in 7H.2, and lifecycle shutdown in 7F.5.)

### Request â†’ Response round-trip (Phase 7F.4)

Phase 7F.4 completes the platform communication round-trip that Phase 7F.3
left as future work â€” the **Request â†’ Response backbone contract**, on top
of the frozen backbone (no redesign: the existing routing and validation
stay authoritative, and no second messaging system exists):

```
PlatformInterface
   â†“  (Request, correlation id)
Platform Backbone        dispatch â€” transport Â· target resolution Â· delivery
   â†“
Target Authority         (domain ownership Â· forwards to its owned service)
   â†“  (invocation)
Owned Service            (domain work Â· ServiceResult)
   â†“  (ServiceResult â†’ Response conversion)
Response                 (explicit Response message, echoes the correlation)
   â†“  (reply â€” the existing response routing)
Platform Backbone
   â†“
Caller                   (receives the correlated Response)
```

* **Request** â€” a `BackboneMessage` of kind `Request` with a concrete target
  and a fresh, opaque **correlation identifier** (`CorrelationId`, minted by
  a deterministic `CorrelationSequence` owned by the requesting endpoint â€”
  no global state, no timestamps, no addresses, no randomness).
* **Response** â€” the explicit `Response` contract: a `BackboneMessage` of
  kind `Response` addressed back to the requesting caller, echoing the
  Request's correlation and carrying an explicit, strongly-typed
  `ResponsePayload` (accepted / completed / rejected / inspected summary â€”
  no `HashMap<String, Any>`, no serialization). A Response is **not** a
  `DeliveryReceipt` (transport outcome) and **not** a `ServiceResult`
  (service outcome): it is the **communication** outcome, produced by the
  explicit `ServiceResult â†’ ResponsePayload` mapping.
* **Correlation** â€” a Response identifies the Request it answers through its
  correlation identifier; a mismatched or missing correlation is rejected
  (`HubError::CorrelationMismatch`). Correlation is the smallest explicit
  mechanism the round-trip requires.
* **Orchestration** â€” the synchronous, deterministic round-trip lives in
  `SySS::request`: dispatch the Request, invoke the target authority's
  service, convert the `ServiceResult`, verify the correlation, deliver the
  Response back with `reply`, and return it to the caller. No async runtime,
  no queues, no threads, no networking, no message persistence.
* **Proof** â€” `PlatformInterface::inspect_workspace()` is the single proof
  operation: `Request(Workspace::Inspect)` â†’ Backbone â†’ Workspace Authority
  â†’ Workspace Service â†’ `ServiceResult::Inspected` â†’ `Response` â†’ caller.
  The existing service accessors (workspace, project, package, settings,
  history, log) also complete the full round-trip.

Richer domain response payloads, asynchronous messaging, queues, message
persistence and distributed transport remain future work.

### Platform lifecycle & safe shutdown (Phase 7F.5)

Phase 7F.5 completes the platform lifecycle that Phases 7Dâ€“7F.4 left
partial. Startup already moved authorities `Registered â†’ Initialized â†’
Active`; 7F.5 adds the controlled **suspend / resume** cycle and the
**deterministic shutdown**, on top of the frozen kernel, backbone and
service architecture (no second lifecycle system, no second error system,
no async teardown).

**Platform lifecycle** (driven by SySS, reflected in `PlatformState`):

```
Starting â†’ Running â‡„ Suspended â†’ ShuttingDown â†’ Stopped
```

**Authority lifecycle** (the single validated transition table,
`HubLifecycle::can_transition`, applied by the one transition mechanism
`HubAuthority::transition`):

```
Registered â†’ Initialized â†’ Active â‡„ Suspended â†’ Shutdown
```

Allowed: `Registered â†’ Initialized`, `Initialized â†’ Active`, `Active â†’
Suspended`, `Suspended â†’ Active`, `Active â†’ Shutdown`, `Suspended â†’
Shutdown`. Everything else â€” including any transition out of `Shutdown` â€”
is rejected with `HubError::InvalidTransition`. Transition logic is never
duplicated across authorities.

**Ownership of lifecycle control:**

* **Platform Kernel** â€” aggregate platform lifecycle: `Kernel::suspend` /
  `resume` / `shutdown` transition the whole authority set together
  (all-or-nothing: every authority is validated before any authority
  moves, so a single authority never transitions the platform into an
  inconsistent state).
* **Authority** â€” domain lifecycle (the validated per-authority states).
* **Service** â€” availability / readiness, synchronized through the
  authority's invocation gate: Active â†’ ready, Suspended â†’ unavailable
  (state preserved), Shutdown â†’ unavailable permanently.
* **Backbone** â€” communication gate: the existing per-authority `Active`
  gate is the one lifecycle gate. While suspended or shut down no
  authority is `Active`, so dispatch/reply reject normal traffic with
  `HubError::InactiveTarget` (no fabricated delivery receipts) and a
  broadcast reaches zero authorities.
* **PlatformState** â€” the platform lifecycle state (validated
  `PlatformState::transition`).
* **Bootstrap** â€” startup / shutdown orchestration only.

**Suspend vs shutdown:** suspension is **pause** â€” `PlatformInterface::
suspend` moves the state to `Suspended`, every authority to `Suspended`,
and normal requests are rejected, but **domain state is preserved** and
`resume` restores the same state (`open workspace â†’ suspend â†’ resume â†’
inspect workspace` still returns the opened workspace). Shutdown is
**termination**: `Bootstrap â†’ PlatformInterface â†’ SySS â†’ Kernel â†’
Authorities â†’ Services â†’ Backbone â†’ Platform State â†’ Stopped`, the handle
is consumed (single-owner shutdown, exactly once), authorities are
`Shutdown`, services can never execute again and the backbone rejects all
normal traffic.

The shutdown ordering is deterministic: 1. stop accepting new normal
requests (state â†’ `ShuttingDown`), 2. shut down the kernel's whole
authority set (`Active | Suspended â†’ Shutdown`; services stop, backbone
participation ends), 3. state â†’ `Stopped`. `ra-persistence`, PSS, Recovery
and RA Core are **not** shut down here â€” those integrations remain future
work.

### Storage boundary audit & foundation (Phase 7G)

Phase 7G audits the existing storage stack and establishes the **storage
boundary foundation** â€” the minimum supported by the implementation. It
implements **no** FSS/PSS/Recovery and no persistence engine: the audit
found that the storage architecture already exists and is reused.

**Audit result â€” what actually exists:**

| Component | Status | Ownership |
|-----------|--------|-----------|
| File/storage-system boundary | `Syss` â€” the System Storage Space | `ra-syss` (`syss.rs`): storage root, 8 categories, device files, atomic writes, import/export |
| PSS | `Pss` â€” Program Serialization Service | `ra-syss` (`pss.rs`): codec registry over the `ra-persistence` codec layer, stream import/export |
| Recovery | `Recovery` + `RecoveryReport` | `ra-syss` (`recovery.rs`): crash recovery for interrupted `*.ra-tmp` writes |
| Codec layer / artifact model | `Serializer`/`Deserializer`/`Validator`, `Artifact`, `Format`, `FileType`, LPM, snapshots | `ra-persistence` |
| Storage vocabulary | `StorageCategory` (8 categories) | `ra-syss` (`storage.rs`, since Phase 7C.1) |
| Storage errors | `ra_syss::Error` (`Persistence`/`Io`/`InvalidName`/`NotFound`/`AlreadyExists`/`Kernel`) with the `From<ra_persistence::Error>` bridge | `ra-syss` |

**FSS is not a separate component in the implementation.** The file/storage-
system boundary of the architecture is `Syss`; the docs' "future FSS
integration" prose means wiring the platform-facing Storage Service to this
existing layer. `StorageCategory` ownership already migrated to `ra-syss` in
Phase 7C.1 â€” no migration was needed in Phase 7G.

**Actual storage architecture (documented as implemented):**

```
PlatformInterface
   â†“  (Request + target + operation + correlation id)
Platform Backbone
   â†“
StorageAuthority        platform ownership of the storage domain
   â†“
StorageService          platform-facing storage service (domain state)
   â†“  (representation; live wiring is the next phase)
Syss Â· Pss Â· Recovery   the ra-syss storage stack (the de-facto FSS)
   â”‚        â”‚
   â”‚        â””â”€ ra-persistence   codec layer / artifact model (bytes only)
   â†“
Persistent Storage      the filesystem boundary lives in Syss
                        (atomic writes, categories, device files)
```

**What Phase 7G changed (minimum foundation):** the Storage Service's
domain state (a `StorageState` over the storage stack `Syss/Pss/Recovery`
and the `StorageCategory` vocabulary) replaces the stale proof capability
string, so the service now *represents* the existing storage architecture
instead of reporting "integration pending". It absorbs **no** persistence
behavior â€” no bytes, no paths, no filesystem access â€” and all platform
storage operations stay behind `StorageAuthority` (never
`PlatformInterface â†’ ra-persistence` / `filesystem` / `PSS` / `Recovery`,
never `Service â†’ Service`). The storage Request â†’ Response round-trip,
correlation, error boundary (service rejections surface as `Rejected`
responses; persistence errors would cross via `Error::Persistence`) and the
Phase 7F.5 lifecycle gates (Running â†’ available, Suspended â†’ blocked,
Resumed â†’ available, Shutdown â†’ blocked) are proven by tests.

**Next phase (storage integration):** wire live storage operations â€” `Save`
/ `Load` through `Syss`/`Pss` and `Recover` through `Recovery` â€” behind the
Storage Authority, with the storage root supplied by the boot chain, plus a
`storage()` accessor on the (currently frozen) `PlatformInterface` surface.

### Storage root + save/load/recovery integration (Phase 7G.1)

Phase 7G.1 connects the Phase 7G storage boundary to the existing storage
implementation â€” the first **real storage integration** of the platform:

```
PlatformInterface
   â†“  Request (Save / Load / Recover / Inspect) + target + correlation id
Platform Backbone
   â†“
StorageAuthority          platform ownership of the storage domain
   â†“
StorageService            the real storage stack (Syss Â· Pss Â· Recovery)
   â†“  Save â†’ Pss (validate+serialize) â†’ Syss (atomic write)
   â†“  Load â†’ Syss (read) â†’ Pss (deserialize)
   â†“  Recover â†’ Recovery::recover (resolve *.ra-tmp)
ra-persistence             codec layer / artifact model (bytes only)
   â†“
Persistent Storage         the filesystem boundary lives in Syss
```

**Storage-root ownership (Task 1â€“2):** `SySS` owns the resolved storage
root internally. [`SySS::initialize`] resolves it deterministically (the
`RA_STORAGE_ROOT` environment variable, else `<cwd>/ra-data`), validates it,
creates the root and every storage category directory through
`Syss::ensure`, runs **startup crash recovery** through `Recovery`, and
**fails the boot** through the existing `ra_syss::Result/Error` boundary
when the root cannot be established or recovery cannot complete. The root is
never exposed through `PlatformInterface`, callers never provide arbitrary
paths, and there is no global mutable storage state.

**Boot-chain threading (additive, frozen signatures intact):** the resolved
root travels down the storage boundary through new additive constructors
only â€” `StorageService::with_root` â†’ `StorageAuthority::with_storage_root`
â†’ `BuiltinAuthorities::with_storage_root` â†’
`KernelInitializer::initialize_with_storage`. Every frozen no-argument
constructor (`new()` / `initialize()`) resolves the platform default root
and is unchanged; no frozen signature was redesigned.

**StorageService operations (Tasks 4â€“7):** the Storage Service performs the
real operations through the existing stack â€” `Save` validates and
serializes the artifact with PSS then stores the bytes with Syss, `Load`
reads with Syss and deserializes with PSS (format resolved from the name
extension), and `Recover` runs the existing `Recovery::recover` over the
root. No new file format, no JSON, no ad-hoc serialization, no duplicate
codec behavior, and no bypass of existing validation (`Syss` path/name
validation and PSS codec validation are both preserved).

**Error boundary (Task 8):** storage failures stay deterministic service
failures â€” the underlying `ra-syss` storage error (ra-persistence wrapped as
`Error::Persistence`, `Error::Io`, `Error::InvalidName`, `Error::NotFound`)
stays at the Syss/Pss/Recovery layer, and the Storage Service answers the
operation with `ServiceResult::Rejected`, which travels back as a
`Rejected` Response. Transport success never means storage success. No new
error types were introduced.

**Response payloads (Task 9):** the Phase 7F.4 Response architecture is
reused. `Save â†’ Completed / Rejected`, `Load â†’ Loaded(representation) /
Rejected`, `Recover â†’ Recovered(report summary) / Rejected` â€” small,
strongly typed additions to `ServiceResult` / `ResponsePayload`. No files,
paths, codec internals or Recovery internals cross the platform boundary.

**PlatformInterface (Task 10):** [`PlatformInterface::storage`] is the
**single public storage entry point** â€” an inspection through the backbone
(mirroring the other service accessors). It never exposes the Storage
Service or the storage root; real Save/Load/Recover ride the backbone
behind it and are proven by the platform tests.

**Lifecycle (Task 3):** storage follows the Phase 7F.5 lifecycle â€” Running â†’
storage available; Suspended â†’ normal storage operations rejected by the
backbone gate (no storage operation executes, no state destroyed); Resumed
â†’ available again; Shutdown â†’ no new storage operations. Shutdown closes
platform participation, it never deletes storage data.

**Tests:** service-level (real save/load/recover through `Syss`/`Pss`/
`Recovery` over isolated roots, unsafe-name rejection, missing-entry
rejection, recovery of interrupted writes) and platform-level (root
established at startup, startup crash recovery, invalid-root boot failure,
Save â†’ Load round-trip with correlation through the backbone, Recover
round-trip, storage errors as `Rejected` responses, lifecycle gating, data
survives suspend/shutdown).

**Status:** `Save integrated` / `Load integrated` / `Recovery integrated` â€”
all three reach the existing implementation and are proven by tests. FSS
remains not-a-separate-component: `Syss` is the file/storage-system
boundary. Not implemented: real FSS beyond Syss, PSS/Recovery internals
changes, message persistence, serialization formats, and any platform
storage UI.

### Active objects & document operations (Phase 7H)

Phase 7H replaces the no-op document operations with the first genuine
**application-level active objects** of the platform â€” real runtime objects,
not name selections, path values, metadata or service state:

```
PlatformInterface            open / close / save / save_as / import / export
   â†“  (Request + target + operation + correlation id)
Platform Backbone            the single message transport
   â†“
Owning Authority             WorkspaceAuthority (workspace + document),
                             ProjectAuthority, PackageAuthority
   â†“
Owning Service               WorkspaceService / ProjectService / PackageService
   â†“  (active object management)
Active Object state          Workspace / Project / Package / Document objects
   â†“  (persistence where required â€” the document domain)
Syss Â· Pss                   the existing storage stack (atomic writes, codec)
   â†“
ServiceResult â†’ Response     correlated response back to the caller
```

**Active object identity:** every object carries a stable, strongly-typed
[`ActiveObjectId`] â€” an [`ActiveObjectKind`] plus a **validated** name. The
name goes through the platform's single name-validation rule (the same rule
`Syss` applies to storage entries), so an identity can never carry a
storage-invalid or path-traversal name. Identity is deterministic and
comparable: equal kind+name pairs denote the same object.

**Ownership map:**

| Object | Owning domain | Service | Notes |
|--------|---------------|---------|-------|
| Workspace | Workspace hub | WorkspaceService | owns the platform's active document too |
| Project | Project hub | ProjectService | records the workspace it was opened inside |
| Package | Package hub | PackageService | records the project it was opened inside |
| Document | Workspace hub | WorkspaceService | the initial hub set has no Document hub; the workspace owns the loaded document (the SySS "files loaded into the IDE" vocabulary) |

No active object owns an authority; no service bypasses its owning
authority; no `PlatformInterface` method touches the filesystem, PSS,
persistence or object internals directly â€” everything stays behind the
backbone.

**Lifecycle model:** the minimal validated lifecycle the operations require
â€” `Closed â‡„ Open` â€” via the single transition table on the object core:
`open` is legal on a `Closed` object, `close`/`save`/`save_as`/`import`/
`export` on an `Open` one, and every other pair is rejected
deterministically. An absent object **is** the `Closed` state; no extra
lifecycle states are invented. `Workspace â†’ Project â†’ Package` containment
is recorded at open time through the request itself (`OpenIn`); no service
reads another service's state.

**PlatformInterface (real since Phase 7H):** `open()`, `close()`, `save()`,
`save_as()`, `import()` and `export()` travel the Request â†’ Response path
through the Platform Backbone to the Workspace Authority, whose service
manages the real `Document` object. `open` brings a device file into the
platform (the existing `Syss::import` *Device File â†’ SySS* step), loads and
deserializes it through PSS (`.ra` text documents; binary encodings still
report `EncodingNotSpecified` at the codec layer and are honestly rejected),
and opens the object. `save`/`save_as` serialize the document's current
content with PSS and write it atomically through `Syss` (into the `files`
category; `save_as`/`export` additionally copy to a device file). `import`
brings a device file into the `files` category without opening it. `theme`,
`view` and the execution-control operations remain contracts.

**Workspace / Project / Package:** the services own real `Workspace`,
`Project` and `Package` objects behind their authorities (`Open` opens
standalone, `OpenIn` opens inside the parent object, `Close` closes,
`Inspect` answers with the object's state summary). The workspace object
replaces the Phase 7F.3 name-only selection state. Since Phase 7H.1 the
open state of these objects **persists** through the existing Syss/PSS
stack (see *Workspace / Project / Package persistence* below); the
persisted workspace/project/package *entries* remain storage-category data
written by their owning services.

**Errors:** the existing error vocabulary is reused. Invalid identities
report [`Error::InvalidName`] at the object layer; every active-object
condition that no storage or kernel error can express (opening an
already-open object, closing a nonexistent object, no document open)
reports [`Error::ActiveObject`] â€” and across the service boundary all of
them become deterministic `Rejected` responses, never panics, never
fabricated successes. No new error types beyond `Error::ActiveObject` were
introduced.

**Lifecycle & shutdown:** active objects are unavailable while their owning
authority is Suspended or Shutdown â€” the existing backbone `Active` gate
rejects the request before any object operation runs; suspension preserves
the object state for resume; shutdown releases the objects deterministically
with the authority teardown.

**Tests:** identity (stability, domain ownership, invalid-name rejection),
object lifecycle (open/close validation, duplicate-open and close-without-
open rejection), workspace/project/package (open, inspect, close, ownership,
association), document (open/load, inspect, modify, save, save_as, close,
import, export, missing files, unsupported formats), integration (full
Request â†’ Response round-trips with correlation through the backbone,
Active Object â†’ Syss/PSS persistence, suspend rejects / resume restores /
state preserved, shutdown rejects), and security (path-traversal rejection,
invalid names and targets, no filesystem access outside `Syss`).

**Status:** `Workspace` / `Project` / `Package` / `Document` active objects
landed; the `PlatformInterface` document operations are real; Phase 7H.1
persists the workspace/project/package objects through the existing stack
(see below); Phase 7H.2 makes Settings/History/Log real persisted
platform-state domains and the theme/view operations real settings-backed
state (see below). Not implemented: the device connector, the RA Core
Gateway, and RA Core itself.

### Workspace / Project / Package persistence (Phase 7H.1)

Phase 7H.1 closes the only persistence gap left by Phase 7H: the
workspace, project and package active objects now persist their domain
state through the **existing** Syss/PSS stack â€” no second storage system.

**Persistence ownership** stays exactly the frozen chain:

```
PlatformInterface â†’ Backbone â†’ Authority â†’ Service â†’ Active Object state
    â†’ Syss (atomic writes) / PSS (`.ra` text codec) â†’ storage root
```

* The **Active Object** remains pure domain/runtime state (identity +
  lifecycle + recorded parent association). It performs no filesystem
  access.
* The **Service** owns the persistence orchestration: on `Open` it loads
  the persisted state (if present), verifies it, reconstructs the object,
  and writes the state atomically; on `Close` it only closes the runtime
  object.
* **Syss** writes atomically (temp file + fsync + rename) into the existing
  categories; **PSS** serializes/deserializes through the existing `.ra`
  text codec; **Recovery** resolves interrupted `*.ra-tmp` writes at
  startup, before any service sees the root.

**Storage categories** (the existing vocabulary): `workspaces/` for
workspace objects, `projects/` for project objects, `packages/` for package
objects. No new root, no new abstraction.

**Object reconstruction:** each object's persisted state is a small
deterministic text (serialized through the `.ra` codec):

```text
workspace: <name>
project:  <name>          (+ optional `in: <workspace>` line)
package:  <name>          (+ optional `in: <project>` line)
```

The entry name is the object name; the optional `in:` line records the
parent association. Opening loads the state when present (missing state
opens fresh), verifies the kind and name, and restores the recorded parent
association â€” so reopening a project standalone after a close (or after a
platform restart) restores its workspace association. The recorded
association is **authoritative**: a requested parent that conflicts with it
is rejected deterministically (an invalid association, never silently
ignored). Corrupt or mismatched persisted state â€” undecodable bytes, wrong
kind, mismatched name, invalid parent â€” is a deterministic rejection.

**Atomic writes & recovery:** persistence uses the existing
[`Syss::save`] atomic-write path; an interrupted write leaves a `*.ra-tmp`
sibling that the existing [`Recovery`] pass resolves at the next startup
(roll forward when no final file exists, remove as stale otherwise). No
second recovery mechanism.

**Lifecycle behavior:** `Closed â‡„ Open` is unchanged. Opening an
already-open object is rejected; closing never deletes the persisted state;
shutdown never deletes it either â€” after a restart the state is restored
through the normal open path. Suspended authorities reject operations at
the existing backbone `Active` gate; resume restores availability and the
preserved state.

### Settings / History / Log persistence + Theme/View foundation (Phase 7H.2)

Phase 7H.2 completes the remaining SySS application-state foundation:
**Settings**, **History** and **Log** become real, persisted platform-state
domains (platform services/state domains â€” **not** Active Objects), and
`theme`/`view` become real settings-backed platform-state operations.

**Ownership** stays the frozen chain â€” `SettingsAuthority â†’ SettingsService`,
`HistoryAuthority â†’ HistoryService`, `LogAuthority â†’ LogService`, all
persisting through the existing stack (`Service â†’ Syss/PSS â†’ storage root`).
No service reads another service's state; no interface or authority bypasses
the backbone. SySS owns these domains (application/platform control); RA
Core is never involved.

**Settings:** a controlled key/value map with deterministic defaults
(`theme` â†’ `light`, `view` â†’ `editor`), validated values (`theme` âˆˆ
`light`/`dark`, `view` âˆˆ `editor`/`terminal`/`ide`; generic keys accept any
non-empty value free of line breaks/NUL), and per-key persistence â€” each key
is one file in `settings/`, written atomically. Operations: `Set`
(validate + persist), `Get` (persisted value or deterministic default),
`Inspect`.

**History:** an ordered list of recorded **platform** operations
(application/platform history â€” explicitly not RA runtime/execution
history), persisted as one line per entry in `history/history`. Operations:
`Record` (validate + persist), `Clear` (removes the persisted state),
`Inspect`. The caller provides the entry explicitly; the service never
inspects Workspace/Project/Package state.

**Log:** the smallest real platform logging subsystem â€” an ordered list of
structured records (`LogRecord`: deterministic 1-based sequence,
`LogSeverity` âˆˆ Info/Warning/Error, source/domain, message), persisted as
one `<severity> <source> <message>` line per record in `logs/log`.
Operations: `Record` (back-compatible `Info` message from the log domain),
`RecordLog { severity, source, message }` (structured), `Clear`, `Inspect`.
The Phase 7F.1 proof behavior is preserved; no external logging dependency.

**Loading is lazy** (on the first operation), so corrupt persisted state
never fails the boot â€” it rejects the first settings/history/log access
deterministically. Persistence uses the existing `Syss::save` atomic-write
path and the `.ra` text codec; interrupted writes are resolved by the
existing startup `Recovery` pass. Suspended/Shutdown authorities reject
through the existing backbone `Active` gate; resume restores the preserved
state.

**Theme/View:** application/UI platform state owned by Settings. The frozen
`PlatformInterface::theme()` / `view()` accessors are real since 7H.2
(retrieval through the settings round-trip), with the additive
`get_theme`/`set_theme`/`get_view`/`set_view` for retrieval and validated
updates. No rendering, no CSS/colors/widgets, no GUI framework â€” the
Frontend consumes the platform state later.

### Authority ownership

The platform ownership chain is fixed:

```
Authority â†’ State â†’ Services â†’ Events â†’ Policies
```

An authority owns exactly one domain and owns that domain's state, services,
events and policies. **Services never own authorities** â€” an authority owns
its services, never the other way around. The backbone dispatches to
authorities; services are reached through their owning authority, never
directly.

### RA Core Gateway & Runtime foundation (Phases 7J / 7J.1)

The **RA Core Gateway** (`ra-gateway`, Phase 7J) is the single
contract-only boundary between SySS and RA Core: backbone messages bound for
execution leave the Platform Backbone through the gateway, which owns the
boundary to RA Core. The **Runtime foundation** (`ra-runtime`, Phase 7J.1)
implements the gateway from the RA Core side: the Execution Manager (owning
execution identity and lifecycle state, and the memory access), and the
REI-provider abstraction over pre-lowered REI. The Execution Manager
interacts with Memory **only through the Execution â†” Memory Gateway** â€”
see below.

The following decisions are **frozen** (Phase 7J.1 + Execution â†” Memory
Gateway):

1. `ra-runtime` is **rank 2, sibling to `ra-syss`**.
2. `ra-runtime` may depend on `ra-gateway`, `ra-memory-gateway`,
   `ra-persistence` and `ra-common` â€” and on nothing else. It **must not
   depend on `ra-memory`**: memory is reached only through the Execution â†”
   Memory Gateway contract.
3. `ra-syss` MUST NOT depend on `ra-runtime`.
4. `ra-bootstrap` and `software` MUST NOT depend on `ra-runtime`.
5. The future **application shell is the composition root**: it builds the
   Execution Manager and injects it into SySS.
6. SySS receives the Gateway through **additive dependency injection** â€”
   `SySS::initialize_with_gateway(Box<dyn Gateway>)` â€” without changing the
   frozen existing initialization signatures.
7. Phase 7J.1 scope is the **REI-provider â†’ ProgramSpace â†’ ExecutionManager**
   path: load, inspect, lifecycle transitions (state-only) and ordered
   shutdown. Nothing executes REI.
8. `FreezeSnapshot â†’ REI` is explicitly deferred until **Phase 7L** compiler
   work.
9. No changes to `ra-gateway`, `ra-memory` or `ra-persistence`.
10. No Execution hub is added to the frozen SySS hub graph.

**Execution â†” Memory Gateway** â€” the **Memory Gateway** (`ra-memory-gateway`,
rank 1) is the dependency-free contract of exactly six operations:
`initialize` (start runtime memory + Program Space), `load_module` (the
single population path of Program Space), `module_by_name`, `module`
(trimmed metadata â€” no addresses), `teardown` (ordered: Program Space
destruction before Memory Manager shutdown) and `live_allocations`. It
carries only contract-owned value types (`ModuleId`, `LoadedModule`,
`CodeMapEntry`, `ModuleRecord`, `MemoryReport`, `MemoryError`) â€” no
`MemoryManager`, no `ProgramSpace`, no `LogicalAddress`, no read/write/
allocate/deallocate surface. The **Memory Adapter** (`ra-memory-gateway-adapter`,
rank 2, the relocated Runtime Loader logic) implements the contract over the
existing `ra-memory` and is injected into the Execution Manager as
`Box<dyn MemoryGateway>` from the composition root. `ra-runtime` and the
adapter are both rank 2 and never depend on each other.

Execution Manager behavior: `Load` resolves a `ProgramId` through the REI
provider and loads the module into Program Space through the memory gateway
(the only population path), minting an `ExecutionId`; `Inspect` reports the
loaded module and execution; `Run` / `Pause` / `Resume` / `Stop` apply the
single validated execution-lifecycle transition table, state-only;
`shutdown` is terminal and performs the ordered teardown through the
gateway (destroy the runtime spaces, then shut down the Memory Manager â€” a
clean shutdown leaves zero live allocations). Memory failures never cross
the outer gateway: they become deterministic `ExecutionResult::Rejected`
answers carrying `ExecutionFailure` / `FailureCode`; `GatewayError` is
reserved for contract violations.

Cross-layer communication is deliberate: e.g. `ra-syss` depends on
`ra-persistence` for the artifact model, codec layer and format/error
vocabulary, and `ra-persistence` does **not** depend back on `ra-syss`
(`StorageCategory` and the storage-oriented error variants moved into
`ra-syss` in Phase 7C.1 to keep the graph acyclic).

## Enforcement

`scripts/check-architecture.sh` parses every member's `Cargo.toml` and
verifies rules 1â€“6:

```sh
bash scripts/check-architecture.sh
```

It exits `0` when the policy holds and `1` with a per-edge message when it
does not. It is safe to run on every PR:

```yaml
# GitHub Actions (example)
- name: Architecture guard
  run: bash scripts/check-architecture.sh
```

The guard's `RANK` and `FORBIDDEN` tables in `scripts/check-architecture.sh`
are the policy source of truth. Adding a crate or a dependency requires
updating the tables deliberately â€” this is the intended friction point.

## Adding a new crate

1. Add the crate under `software/` and register it in the workspace
   `members` list.
2. Add it to `RANK` (and, if it has forbidden edges, `FORBIDDEN`) in
   `scripts/check-architecture.sh`.
3. Run the guard and `cargo check --workspace` to confirm.

