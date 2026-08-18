# RA-RUST-4D — OG RA CORE COMPLETE FORENSIC SOURCE AUDIT

**Date:** 2026-08-15 · **Mode:** READ-ONLY · **Baseline:** `F:\RA assests\Reference\RA.lang` (the OG RA Core source tree) vs `F:\RA_01` (the current New RA repository)

**Method:** Every subsystem module of the OG tree was read in full (VME engine, decoder, ISA, bytecode chain, GPC, RGC, RMM, EHub, interpreter, compiler backend, CLI/entry points). Every claim below cites its exact source path. Where evidence is absent, the conclusion is marked **NOT ESTABLISHED BY OG SOURCE**.

**Source abbreviations:**
- `VM` = `src/rvm/VME/virtual_machine.py` · `INST` = `src/rvm/VME/instruction.py` · `OPS` = `src/rvm/VME/opcode_table.py` · `DEC` = `src/rvm/VME/decoder.py` · `BR` = `src/rvm/VME/bytecode_reader.py` · `RW` = `src/rvm/VME/rbc_writer.py` · `CB` = `src/rvm/VME/compiler_backend.py` · `FRA` = `src/rvm/VME/frame.py` · `REG` = `src/rvm/VME/registers.py` · `VA` = `src/rvm/VME/vme_gpc_adapter.py` · `RBCA` = `src/rvm/bytecode/vme_rbc_adapter.py`
- `BG` = `src/rvm/bytecode/bytecode_generator.py` · `RC` = `src/rvm/bytecode/rc_restorer.py` · `REA` = `src/runtime/rbc_execution_adapter.py` · `EC` = `src/runtime/execution_context.py` · `EXE` = `src/runtime/executor.py` · `RT` = `src/runtime/interpreter.py`
- `EP` = `src/rvm/gpc/execution_plan.py` · `GM` = `src/rvm/gpc/gpc_manager.py` · `MR` = `src/rvm/gpc/memory_router.py` · `LC` = `src/rvm/gpc/lifecycle.py` · `REG` = `src/rvm/gpc/registry.py` · `RID` = `src/rvm/gpc/rid_discovery.py`
- `ST` = `src/rvm/rgc/state_tracker.py` · `CM` = `src/rvm/rgc/cleanup_manager.py` · `MT` = `src/rvm/rmm/container.py` · `VMEM` = `src/rvm/rmm/variable_memory.py`
- `EH` = `src/EHub/environment_hub.py` · `MAIN` = `src/main.py` · `CLI` = `src/cli_router.py`

---

## PHASE A — COMPLETE INVENTORY

`F:\RA assests\Reference\RA.lang` contains **1,140 Python files** across the tree. The authoritative source tree is `src/` (plus `libraries/`, `tests/`, and packaged copies in `dist/`, `release/`, `PUBLIC_REPO/downloads/` which are byte-identical or near-identical snapshots of `src/runtime`).

### Classification table (src/ — the live source)

| Subsystem | Path | Key files (size) | Purpose |
|---|---|---|---|
| **Lexer** | `src/lexer/` | `tokenizer.py` (18 KB), `tokens.py` (20 KB) | RA source → tokens |
| **Parser** | `src/parser/` | `parser.py` (84 KB), `ra_ast.py` (87 KB), `ast_core.py` | tokens → AST (`ProgramNode`/`Node` family) |
| **Semantic** | `src/semantic/` | `semantic_analyzer.py` (29 KB), `resolver.py` (25 KB), `symbol*.py`, `family.py`, `scope.py` | symbol/scope/family analysis |
| **Compiler front** | `src/compiler/` | `core/io/*`, `internal/*`, `oop/*` (class/method/constructor parsers + AST nodes), `common/pf.py`, `common/property_engine.py` | IO blocks, OOP declaration parsing, PF/property engine |
| **AST Interpreter** | `src/runtime/` | `interpreter.py` (**163 KB**), `control_flow.py` (38 KB), `execution_context.py`, `executor.py`, `gpc_integration.py` (26 KB), `lifecycle_manager.py`, `sdb_engine.py` (41 KB), `db_engine.py`, `pipeline_tracer.py`, `rbc_execution_adapter.py`, DSA engines (graph/tree/stack/queue/deque/sorting/searching), `builtins/`, `oop/`, `structural/` | **Primary execution engine** — tree-walking AST executor |
| **RVM/VME** | `src/rvm/VME/` | `virtual_machine.py` (**53 KB**), `compiler_backend.py` (**82 KB**), `decoder.py`, `bytecode_reader.py`, `rbc_writer.py`, `instruction.py`, `opcode_table.py`, `frame.py`, `operand_stack.py`, `registers.py`, `instruction_stream.py`, `constant_pool.py`, `rvm_object.py`, `exceptions.py`, `vme_gpc_adapter.py` | **Compiled bytecode engine** — fetch/decode/execute VM over `.rbc` |
| **RVM/bytecode** | `src/rvm/bytecode/` | `bytecode_generator.py` (27 KB), `bytecode_loader.py`, `bytecode_validator.py`, `bytecode_writer.py`, `program_graph.py`, `rc_restorer.py` (25 KB), `sc_bytecode_bridge.py` (16 KB), `vme_rbc_adapter.py` (10 KB), `token_mapper.py`, `metabase_rebuilder.py`, `registry_rebuilder.py`, `restoration.py`, `reconstruction.py`, `gpc_restoration_manager.py` | Constitution-token bytecode generation, loading, reconstruction, restoration |
| **RVM/GPC** | `src/rvm/gpc/` | `execution_plan.py` (32 KB), `lifecycle.py` (28 KB), `gpc_manager.py` (15 KB), `memory_router.py` (15 KB), `gbetabase.py`, `ghost_metabase.py` (6 KB), `gmetadata.py` (19 KB), `registry.py` (10 KB), `rid_discovery.py`, `sml.py` | **Global Program Context** — RID, Registry, Metabase, Betabase, SML, LifecycleCoordinator, ExecutionPlanner |
| **RVM/RGC** | `src/rvm/rgc/` | `state_tracker.py`, `cleanup_manager.py`, `reload_manager.py`, `transfer_manager.py` | **Lifecycle authority** — Ç/Å/⟩/‽/Â/¡ state machine, PC→SC cleanup, reload, transfer |
| **RVM/RMM** | `src/rvm/rmm/` | `container.py` (MemoryTriple), `variable_memory.py`, `object_memory.py`, `method_memory.py`, `dsa_memory.py`, `library_memory.py`, `ghost_memory.py`, `variable_manager.py` | **Memory manager** — six name-keyed RC/PC/SC domains |
| **EHub** | `src/EHub/` | `environment_hub.py`, `environment_registry.py`, `environment_context.py`, `base_coordinator.py` + coordinators for BE, EE, GPC, LE, PE, RADE, RAPG, RARE, RE, SE | **Environment Hub** — coordinates (never compiles/executes/parses) |
| **RADE** | `src/RADE/` | `diagnostic_codes.py` (26 KB), `diagnostic*.py`, `recovery_engine.py`, `specification_reference.py` | RA Diagnostic Engine — error codes/diagnostics |
| **Program mgmt** | `src/rare/`, `src/radk/`, `src/rapm/`, `src/rarg/`, `src/resolver/`, `src/cf/` | `rare/cli/project_cli.py`, `radk/cli/radk_cli.py` (45 KB), `rapm/package_manager.py`, `rarg/rule_engine.py`, `cf/*` | Project/package CLI, dev kit, package manager, relationship/pattern analysis |
| **Debugger** | `src/debugger/` | `debugger.py` (26 KB), `debug_session.py`, `breakpoint_manager.py`, `execution_trace.py` | Observational debug hooks (`pre_execute_node`/`post_execute_node` — RT) |
| **IDE** | `src/ide/` | `ui/window.py` (93 KB), `ui/editor/editor.py` (64 KB), `services/*`, `bridge/compiler_bridge.py` | RA Studio IDE |
| **LSP** | `src/lsp/` | `language_server.py` (36 KB), `workspace_manager.py`, `document_manager.py` | Language server |
| **Entry** | `src/main.py`, `src/cli_router.py` | — | REPL / file execution / mode dispatch |
| **Tests** | `tests/` | **400+ files** (e.g. `test_vm_*.py`, `test_rbc_*.py`, `test_compiled_*_execution.py`, `test_gpc_*`, `test_rmm_memory.py`, `test_rgc.py`, `test_rc3_05*`, `test_rc3_06*`) | Full regression suite for every subsystem |
| **Libraries** | `libraries/` | `core/` (19 KB), `db/` (17 KB), `io/` (14 KB), `math/` (10 KB), `Collections/`, `Measurement/`, `pf/` | RA standard-library surface |

**Notable:** `src/rvm/__init__.py`, `src/rvm/rmm/__init__.py`, `src/rvm/rgc/__init__.py` are **empty**; the subsystem namespaces are exported from the individual modules.

---

## PHASE B — OG RA CORE ARCHITECTURE (from source)

### Subsystem-by-subsystem

**1. RVM — RA Virtual Machine** (`src/rvm/`). Umbrella namespace. Contains VME (execution engine + ISA + compiler backend), bytecode (generation/reconstruction/restoration), gpc, rgc, rmm, engine.
- *Owns:* nothing itself (empty `__init__.py`).
- *Never owns:* state — it is a package, not an object.

**2. VME — Virtual Machine Engine** (`src/rvm/VME/`, `VM`). `VirtualMachine` class: classic fetch-decode-execute loop (`while self.running: instr = self.stream.next(); self.execute(instr)`).
- *Owns:* `OperandStack` (bounded, default depth 4096), `ConstantPool`, `frames: List[Frame]` (call stack), `Registers` (reserved, unwired), `InstructionStream` (cursor), output buffer, step counter, optional `VMEAdapter`.
- *Inputs:* decoded `List[Instruction]` (`load_bytecode`) or `.rbc` bytes (`load_bytes`/`load_program`).
- *Outputs:* captured output (`get_output()`), final stack/frame state, `running` flag.
- *Lifecycle:* `run()` → `HALT`/`RETURN`@root/stream-end/`VMError`; `reset()` clears everything.
- *Dependencies:* VME modules only; optional GPC via `VMEAdapter`.
- *Never owns:* GPC state, Registry, RMM memory, compiler.

**3. GPC — Global Program Context** (`src/rvm/gpc/`). The identity/metadata/lifecycle authority stack.
- **RIDDiscovery** (`RID`): per-type sequential identity generator `{prefix}{hint}-{seq}` (e.g. `C<U>-1001`).
- **Registry** (`REG`): RID → `{rid_type, state, location}` + optional GMetadata sidecar. Stores **no** source, bytecode, or relationships.
- **GhostMetabase**: entity relationship store (PARENT/CHILD/DEPENDENCY/OWNERSHIP/REFERENCE).
- **GBetaBase**: background provenance (DERIVATION relations).
- **GMetadata / MetadataFactory**: descriptive metadata records; `MetadataDomain` = VARIABLE/OBJECT/METHOD/DSA/LIBRARY_PACKAGE/GPC.
- **SML**: change authority (records implemented changes only).
- **LifecycleCoordinator** (`LC`): orchestrates create/derive/modify flows across RID+Registry+SML+GBetaBase+Metabase+MemoryRouter+StateTracker. Pure orchestration — duplicates no sub-system.
- **MemoryRouter** (`MR`): GPC→RMM routing — maps `MetadataDomain` to the correct RMM component; provides `place/update/resolve/remove/exists` and batch `promote_all/save_all/restore_all_from_production/clear_rc`.
- **ExecutionPlanner** (`EP`): builds pure-metadata `ExecutionPlan` (units, dependency groups, topological order, INTERPRET/COMPILE mode) consumed by both Interpreter and CompilerBackend.
- **GPCManager** (`GM`): facade over all of the above (`create_class/method/variable/object/table/cx/cs/ca/cm`).
- *Owns:* RID counters, registry entries, metadata, relations.
- *Never owns:* RA memory values (those live in RMM), bytecode, VM execution state.

**4. RGC — Runtime Garbage Collection / lifecycle** (`src/rvm/rgc/`). **StateTracker** (`ST`) is the **lifecycle authority**: states `Ç` (Created), `Å` (Active), `⟩` (Frozen), `‽` (Dead), `Â` (Archived), `¡` (Deleted, terminal) with a validated transition table (`_VALID_TRANSITIONS`). **CleanupManager** (`CM`) orchestrates PC→SC (requires ⟩ Frozen; transitions to Â) and discard (Â→⟩). ReloadManager/TransferManager handle reload/transfer workflows. Registry mirrors RGC state one-way via `sync_to` (RGC = authority, Registry = consumer).

**5. RMM — RA Memory Manager** (`src/rvm/rmm/`). **MemoryTriple** (`MT`): `RC` (runtime/edit) / `PC` (placeholder/last stable) / `SC` (static/persisted) with `promote` (RC→PC), `save` (PC→SC), `restore_from_saved` (SC→PC→RC), `restore_from_production` (PC→RC). Six domain components (`VariableMemory` etc.), each a `dict[name → MemoryTriple]`. **Keys are entity names, not RIDs, not addresses** (`MR`: "All RMM components use **name** (not RID) as their storage key").

**6. Bytecode subsystem** (`src/rvm/bytecode/`). **Two distinct bytecode worlds** (critical finding):
- **(a) Constitution token bytecode** (`BG`): `BytecodeEntry{token, values, rid_short}` lines like `CU1001:200:+:v<ag>-7001:500`, generated from Registry (state=A_ARCHIVED, location=SC) + GhostMetabase + SC data. Loaded/validated/written by `BytecodeLoader/Validator/Writer`; reconstructed (Registry/MetabaseRebuilder, ProgramGraph) and restored (`RcRestorer` → `RcProgram/RcMethod`); then **re-executed via the AST interpreter** through `RbcExecutionAdapter → ExecutionContext → Runtime`.
- **(b) VME binary `.rbc`** (`RBCA`): canonical binary format (magic `RABC`, v1.0), produced by `CompilerBackend` (AST→`Instruction[]`), serialized by `RbcWriter`, read by `BytecodeReader`, decoded by `decode_program`, executed by `VirtualMachine`. The `VMEInstructionRBCAdapter` is an explicitly **thin sequencing bridge** between (a)-adjacent systems and (b) — it "does NOT compile AST nodes, execute instructions, manage lifecycle, generate RIDs, own Registry/GPC/RMM".

**7. EHub — Environment Hub** (`EH`). Central coordinator. Constitution: "EHub SHALL ONLY coordinate environments", never compile/execute/parse/generate. Owns `EnvironmentRegistry` + `EnvironmentContext`; `initialize_all()` / `shutdown_all()` drive coordinator lifecycles (reverse order on shutdown). Registered environments: **LE** (lexer), **PE** (parser), **SE** (semantic), **BE** (bytecode), **EE** (execution), **RE** (runtime), **GPC**, **RADE**, **RAPG**, **RARE**.

**8. RC — "RC" has three distinct OG meanings** (must not be conflated):
- (a) **RC slot** = the Runtime/current-working slot of `MemoryTriple` (`MT`).
- (b) **RcRestorer / RcProgram / RcMethod** (`src/rvm/bytecode/rc_restorer.py`) = the "RC Restore" stage that converts a `RestoredProgram` into an AST-executable `RcProgram`.
- (c) **RC2/RC3 sprint prefixes** (e.g. `RC2-07C`, `RC3-05H`) = "Release Cycle" versioning in docstrings/tests. There is **no single ProgramController named "RC"** in the source.

**9. PC — ProgramController / PC slot.** Same ambiguity resolution:
- (a) **PC slot** = Placeholder/last-stable slot of `MemoryTriple`.
- (b) **ProgramController** — the closest real objects are `src/rare/runner/execution_controller.py` (1.7 KB) and `src/EHub/EE/execution_controller.py` (348 B, a stub importing `ProjectExecutor`). No substantive "ProgramController" core exists; project execution is `ProjectExecutor` (`src/rare/executor/project_executor.py`, 10 KB).

**10. RE — Runtime Environment.** `src/EHub/RE/coordinator.py` wraps `src/runtime/interpreter.py`'s `Runtime` class. `RE/interpreter.py` is a 198 B re-export. The **actual runtime** is the `Runtime` tree-walking interpreter (`RT`).

**11. Instruction system** — see Phase D.

**12. Memory system** — see Phase E.

**13. Registry system** — `Registry` (`REG`) as above.

**14. Frame/scope system** — two independent implementations:
- **VME**: `Frame` (`FRA`) = `{name, locals: Dict[str,Any], return_address, stack_base}`; lookup walks frames outward (`_lookup_variable`). Module frame `Frame("<module>")` is the base.
- **Interpreter**: `global_scope: dict` + `_locals: list[dict]` scope stack (`RT`), with function-call isolation (saved globals restored on return).

**15. Bytecode system** — Phase D.

**16. Compiler/runtime boundary** — Phase H.

---

## PHASE C — EXECUTION PIPELINE (as evidenced, not assumed)

The OG Core has **three** execution paths. The canonical compiled path (`CB` docstring) is:

```
RA Source
   ↓  Lexer → tokens            (src/lexer/tokenizer.py)
   ↓  Parser → ProgramNode AST  (src/parser/parser.py + ra_ast.py)
   ↓  CompilerBackend.compile()  (src/rvm/VME/compiler_backend.py)
   ↓  List[Instruction] + ConstantPool
   ├─→ VirtualMachine.run()      (fetch → decode → execute)   [direct path]
   └─→ RbcWriter → .rbc file → BytecodeReader → decode_program → VirtualMachine   [persisted path]
```

**Path A — source/AST (default)**: `main.py _run_file → tokenize → Parser.parse() → Runtime().execute(ast)` (`MAIN`, `RT`). This is the **default CLI path**.

**Path B — compiled .rbc via VME**: `CompilerBackend.compile(program_node) → instructions+constants → (RbcWriter → .rbc) → BytecodeReader → decode_program → InstructionStream → VirtualMachine.run()` (`RBCA`, `VM`, `RW`, `DEC`, `BR`). Used by the compiled-execution test suite (`tests/test_compiled_*_execution.py`, `tests/test_end_to_end_compiled_ra.py`).

**Path C — Constitution token bytecode (archival)**: `Registry(SC) + GhostMetabase + SC provider → BytecodeGenerator → BytecodeEntry[] → (BytecodeWriter → file) → BytecodeLoader → Reconstruction → Restoration → RcRestorer → RcProgram → ExecutionContext.populate_from_rc_program → Runtime.execute(ProgramNode)` (`BG`, `RC`, `REA`, `EC`). **Critical: path C terminates in the AST interpreter — the token bytecode is never executed by a VM; it is restored back into AST nodes and interpreted.**

Every transition and its responsible subsystem is identified above; the sequence is evidenced by `RBCA` ("CompilerBackend = canonical AST→VME Instruction compilation; RbcWriter+BytecodeReader = canonical binary .rbc serialization; VirtualMachine = canonical bytecode execution") and `REA` ("RBC → Loader → Reconstruction → Restoration → RC Restorer → ExecutionContext → Runtime → Executor").

---

## PHASE D — OG INSTRUCTION SYSTEM

**ISA (from `INST` + `OPS` + `DEC`):** 40 canonical opcodes (NOT 43 — the 5D catalog count claimed in the prompt is **not present** in this source; the count is exactly 40, enumerated below).

| # | Opcode | Binary code | Operands | Effect (from `OPS`) |
|---|---|---|---|---|
| 1 | `LOAD_CONST` | `0x01` | 1 (pool index) | Push constant from pool |
| 2 | `LOAD` | `0x02` | 1 (var name) | Push local variable value |
| 3 | `STORE` | `0x03` | 1 (var name) | Pop to local variable |
| 4 | `POP` | `0x04` | 0 | Pop and discard |
| 5 | `ADD` | `0x10` | 0 | Pop two, push sum |
| 6 | `SUB` | `0x11` | 0 | Pop two, push difference |
| 7 | `MUL` | `0x12` | 0 | Pop two, push product |
| 8 | `DIV` | `0x13` | 0 | Pop two, push quotient |
| 9 | `MOD` | `0x14` | 0 | Pop two, push remainder |
| 10 | `EQ` | `0x20` | 0 | Pop two, push `==` |
| 11 | `NE` | `0x21` | 0 | Pop two, push `!=` |
| 12 | `LT` | `0x22` | 0 | Pop two, push `<` |
| 13 | `GT` | `0x23` | 0 | Pop two, push `>` |
| 14 | `LE` | `0x24` | 0 | Pop two, push `<=` |
| 15 | `GE` | `0x25` | 0 | Pop two, push `>=` |
| 16 | `PRINT` | `0x30` | 0 | Pop and print (no newline) |
| 17 | `PRINTLN` | `0x31` | 0 | Pop and println |
| 18 | `JMP` | `0x40` | 1 (addr) | Unconditional jump |
| 19 | `JZ` | `0x41` | 1 (addr) | Jump if zero/false |
| 20 | `JNZ` | `0x42` | 1 (addr) | Jump if non-zero/true |
| 21 | `CALL` | `0x43` | var (addr, argc, param names...) | Call function entry |
| 22 | `RETURN` | `0x50` | 0 | Return from current call |
| 23 | `NEW_OBJ` | `0x60` | 1 (class name) | Create RVMObject |
| 24 | `LOAD_PROP` | `0x61` | 1 (prop name) | Push object property |
| 25 | `STORE_PROP` | `0x62` | 1 (prop name) | Pop value+obj, store property |
| 26 | `CALL_METH` | `0x63` | var (addr, method name) | Call method with `_self` |
| 27 | `NOT` | `0x76` | 0 | Unary logical NOT |
| 28 | `BAND` | `0x80` | 0 | Bitwise AND |
| 29 | `BOR` | `0x81` | 0 | Bitwise OR |
| 30 | `BXOR` | `0x82` | 0 | Bitwise XOR |
| 31 | `BLSHIFT` | `0x83` | 0 | Bitwise left shift |
| 32 | `BRSHIFT` | `0x84` | 0 | Bitwise right shift |
| 33 | `BNOT` | `0x85` | 0 | Bitwise NOT |
| 34 | `STRICT_EQ` | `0x90` | 0 | Strict equality (value + family) |
| 35 | `BOOL` | `0x91` | 0 | Convert to boolean |
| 36 | `INPUT` | `0xA0` | var (input_type, prompt_idx?) | Read from stdin |
| 37 | `CONTAINS` | `0xA1` | 0 | Membership test |
| 38 | `BUILTIN` | `0xB0` | var (method, var_name, *args) | Unified built-in property op |
| 39 | `HALT` | `0xFF` | 0 | Stop the VM loop |
| 40 | `NOP` | `0x00` | 0 | No operation |

**Encoding model (from `DEC` + `RW` + `BR`):**
- **Variable-width, tagged** — not fixed-width, not register-based. Per instruction: `Opcode (uint16) | Operand count (uint8) | tagged operands...`.
- **Operand tags** (`DEC`): `NONE=0`, `BOOL=1` (1 byte), `INT=2` (int64, `<q`, 8 bytes), `FLOAT=3` (double, `<d`, 8 bytes), `STR=4` (uint32 length + UTF-8). Same tag system for constant pool.
- **Binary file** (`BR`/`RW`): 32-byte header — magic `0x52414243` ("RABC"), version major/minor (uint16 each, expected `1.0`), flags (uint16; bit0 big-endian, bit1 debug), reserved (uint16), CP offset (uint32), instruction offset (uint32), 12 bytes padding. Default **little-endian**; big-endian flag bit exists but the decoder always unpacks `"<"` little-endian (endian flag is parsed but **not honored** by `decode_program` — a latent inconsistency).
- **Decoder validation** (`DEC`): unknown opcode → `InvalidOpcode`; truncated header/section → `BytecodeFormatError`; operand-count mismatch vs `opcode_table` (exact or `-1` variable) → `BytecodeFormatError`.
- **Instruction pointer**: `InstructionStream` cursor (`instruction_stream.py`) — `next()` fetches then advances; jumps set the cursor absolutely; `is_end` stops the loop.
- **Frames** (`FRA`): name-keyed locals; `return_address` = stream position; `stack_base` = operand-stack depth at call.
- **Registers** (`REG`): `ACC/TMP/CTR/BASE/SP/FLAGS` reserved but **not wired into dispatch** — documented placeholder ("not yet wired into the instruction dispatch — will happen when the compiler and VM co-evolve to support a register-based IR in a later sprint"). **NOT ESTABLISHED:** any register-based encoding; the ISA is stack-based.
- **Entry point / end-of-program**: entry = address 0; program must end with `HALT` (CompilerBackend always appends `HALT` — `CB`); stream exhaustion also halts. `RETURN` at module level halts.

---

## PHASE E — OG MEMORY (RMM)

- **Model:** six name-keyed domains (Variable/Object/Method/DSA/Library/Ghost), each entity = `MemoryTriple{RC, PC, SC}` (`MT`, `VMEM`).
- **Addressing:** **none** — storage keys are entity *names*; no regions, slots, generations, or pointers anywhere in `src/rvm/rmm/`. `MR` documents: "All RMM components use **name** (not RID) as their storage key."
- **Workflow** (`MT` docstring): `edit → RC; execute → RC→PC (promote); save → PC→SC (save); revert → SC→PC→RC or PC→RC`. `promote_all/save_all/clear_rc/restore_all_from_production` exist as batch operations (`MR`).
- **Ownership:** GPC `LifecycleCoordinator` orchestrates; `MemoryRouter` routes by `MetadataDomain`; RGC `StateTracker` is the lifecycle state authority; `Registry` is the identity authority. The **Runtime/VME never touches RMM directly** — they go through `GPCIntegration`/`VMEAdapter` → `LifecycleCoordinator` → `MemoryRouter` → RMM (`VA`).
- **Cleanup:** `CleanupManager.cleanup` (PC→SC, requires ⟩, sets Â) / `discard` (SC→PC, requires Â, sets ⟩) (`CM`). Entity destruction is `I_DELETED` via `StateTracker` (terminal).
- **Key divergence from New RA:** OG RMM is a name-keyed RC/PC/SC triple store; New RA `ra-memory` is a `LogicalAddress[region|slot|generation]` + `ProgramSpace/ActiveSpace/EntitySpace/GlobalEntityArea/LocalEntityResolver/ValueList` model. These are **different designs** (see Phase I).

---

## PHASE F — OG PROGRAM / EXECUTION MODEL

- **Program identity:** RID (`RID`) — e.g. `C<U>-1001`; per-type sequential counters; also Registry entry (RID → type/state/location).
- **Module identity:** **NOT ESTABLISHED** as a first-class OG concept — programs load as whole `Instruction[]` streams; `Frame("<module>")` is the only module marker (`VM`).
- **Execution identity:** **NOT ESTABLISHED** — no ExecutionId; a VM instance is one execution session; `reset()` prepares reuse.
- **Runtime instance:** `VirtualMachine` (compiled) or `Runtime` (interpreted); `ExecutionContext` unifies both paths (`EC`).
- **Frame identity:** `Frame{name, return_address, stack_base}` (`FRA`).
- **Scope identity:** interpreter `global_scope` + `_locals` stack (`RT`); VME frame-chain lookup (`VM._lookup_variable`).
- **Load:** `load_bytes`/`load_program` (VME), `BytecodeLoader` (token path), `populate_from_rc_program` (`EC`).
- **Unload:** `VirtualMachine.reset()`; no explicit program unload in the token path beyond `Runtime` re-instantiation.
- **Execution lifecycle:** synchronous `run()` to completion (HALT / RETURN@root / stream end / VMError). **Stop/pause/resume are NOT implemented** — no step/pause/resume API exists in `VM` (only `max_steps` safety limit raising `ExecutionLimitExceeded`). The debugger (`src/debugger/`) hooks `pre/post_execute_node` observationally on the **interpreter** path only.
- **Completion:** `running=False` after HALT/end. **Failure:** `VMError` hierarchy (`StackOverflow/StackUnderflow/InvalidOpcode/BytecodeFormatError/InvalidJumpTarget/ExecutionLimitExceeded`).
- **Shutdown:** `VirtualMachine.reset()`; `EnvironmentHub.shutdown_all()` (reverse registration order) (`EH`).

---

## PHASE G — OG LANGUAGE → RUNTIME MAPPING (all evidenced)

| RA construct | Compiler emission (`CB`) | VM handler (`VM`) | Interpreter (`RT`) |
|---|---|---|---|
| Literals | `LOAD_CONST idx` (pool, deduped) | `execute_load_const` | `evaluate(LiteralNode)` |
| Variables (local) | `LOAD name` / `STORE name` | `execute_load`/`execute_store` | `_lookup_identifier`/`_execute_assignment` |
| Assignment | expr + `STORE` | `execute_store` (Frame + GPC lifecycle) | `_execute_assignment` |
| Arithmetic `+-*/%` | `LOAD_CONST+LOAD_CONST+ADD/SUB/MUL/DIV/MOD` | `_binary_arith` (div/mod by zero → VMError) | `_eval_binary_op` |
| Comparison `== != < > <= >=` | same pattern + `EQ/NE/LT/GT/LE/GE` | `_binary_compare` | `_eval_binary_op` |
| Strict compare | `STRICT_EQ` | `execute_strict_eq` (value + family) | `_eval_strict_compare` |
| Boolean/logical | `BOOL`, `NOT`, logical → branch lowering | `execute_bool`, `execute_not` | `_eval_logical`, `_eval_unary_logical` |
| Bitwise | `BAND/BOR/BXOR/BLSHIFT/BRSHIFT/BNOT` | `execute_band...` (int-only) | `_eval_bitwise` |
| Branching `if/elseif/else` | cond+`JZ`+body+`JMP`+patches | `execute_jz`/`execute_jmp` | `ControlFlowEngine.execute_if` |
| Loops `for/while/?in` | canonical loop: init+cond+`JZ`+body+updater+`JMP` | `execute_jz/jmp` + `CONTAINS` | `ControlFlowEngine` (for/while/in/do-while) |
| Break/Continue | `JMP` to loop exit/condition | `execute_jmp` | `BreakException`/`ContinueException` |
| Functions | function pre-scan, skip-JMP, `CALL addr,argc,names...`, `RETURN` | `execute_call` (frame+param bindings), `execute_return` | `FunctionRegistry`, `_call_function` |
| OOP objects | `NEW_OBJ`, `LOAD_PROP`, `STORE_PROP`, `CALL_METH` (compile-time patched addresses) | `execute_new_obj/load_prop/store_prop/call_meth` (`_self` binding) | `oop/*` mixins, `ObjectRegistry` |
| Print | expr + `PRINT`/`PRINTLN` | `execute_print/println` (RA surface formatting) | `_execute_print` |
| Input | `INPUT type[,prompt_idx]` | `execute_input` (injectable stdin) | `_execute_input` |
| Builtins (type/len/abs/round/is/upper/lower/trim/char/first/last/count/find/replace) | `BUILTIN method,var,*args` | `execute_builtin` | dedicated `_execute_*` + `builtins/` |
| Membership `in` | `CONTAINS` | `execute_contains` | `ControlFlowEngine.execute_in` |
| Halt | `HALT` (always appended) | `execute_halt` | n/a |
| Errors | compile-time `CompilerBackendError` | `VMError` hierarchy | `RuntimeError` + RADE diagnostics (`MAIN`) |
| DB / Sdb tables | Constitution tokens `T9xx` (token path `BG`); interpreter executes Sdb ops | n/a (no VM db ops) | `db_engine`/`sdb_engine` |
| Print loops/blocks, `?What/?Which`, PF, CF, complex family, measurements | partial (`CB` complex/Sdb support) | n/a | interpreter-only features |

**Only mappings actually supported by source are listed.** Features marked interpreter-only have **no VM opcode** and therefore no compiled path.

---

## PHASE H — OG COMPILER BOUNDARY

Confirmed pipeline (`CB` docstring): `RA Source → Lexer → tokens → Parser → ProgramNode (AST) → CompilerBackend.compile(program) → List[Instruction] → VirtualMachine.run() → Output` (or `RbcWriter → .rbc`).

- **Artifact produced by the original compiler:** a `(List[Instruction], ConstantPool)` pair, serializable to **binary `.rbc`** (magic `RABC`, v1.0) — NOT REI, NOT a 43-instruction catalog, NOT `.rab/.raf/.rap`. There is a **second, unrelated** artifact: Constitution token `BytecodeEntry[]` text (from `BytecodeGenerator`, `BG`) which is restored back to AST and interpreted (Phase C, Path C).
- **Lexer→Parser→AST→Semantic:** `src/lexer`, `src/parser`, `src/semantic` all exist and feed both the interpreter and `CompilerBackend`.
- **What the compiler does NOT do:** no REI emission, no register allocation (registers are an unwired placeholder), no `.rab/.raf/.rap` encodings (those strings appear nowhere in `src/`), no GC, no threading.

---

## PHASE I — OG VS CURRENT NEW RA (`F:\RA_01`)

New RA verified structure: 72 `.rs` files across `ra-common` (5), `ra-persistence` (8), `ra-memory` (16 + 7 test files), `ra-gateway` (4), `ra-runtime` (5), `ra-syss` (hub 13 + 6), `ra-bootstrap` (8), `software/src/main.rs`. `software/compiler`, `software/ide`, `software/debugger`, `software/cli` are **empty placeholder directories**.

| OG subsystem | New RA component | Status | Evidence |
|---|---|---|---|
| AST Interpreter (`RT`) | — | 🔴 MISSING (no interpreter; only contract-level runtime) | no `.rs` equivalent |
| VME `VirtualMachine` | (target of 7J.2 ExecutionEngine — not yet implemented) | 🔴 MISSING | `ra-runtime` has only `execution_manager/runtime_loader/rei_provider/error` |
| CompilerBackend + .rbc | — | 🔴 MISSING (compiler dir empty) | `software/compiler/` empty |
| ISA (40 opcodes) | — | 🔴 MISSING (REI model still undefined in code) | `rei_provider` returns opaque bytes |
| Lexer/Parser/Semantic | — | 🔴 MISSING | dirs empty |
| RMM (RC/PC/SC triples) | `ra-memory` (LogicalAddress, spaces, ValueList) | 🔵 INTENTIONALLY REPLACED | address/space model differs fundamentally |
| Registry + RID | `ActiveObjectId` (validated kind+name), backbone authorities | 🟡 PARTIALLY PRESERVED (identity concept kept; format/type model redesigned) | `hub/active_object.rs` |
| RGC StateTracker lifecycle | backbone `Active` gate + authority Suspended/Shutdown | 🟡 PARTIALLY PRESERVED (concept kept; states redesigned) | `hub/lifecycle.rs` |
| GPC LifecycleCoordinator/MemoryRouter | (no equivalent) | 🔴 MISSING | — |
| EHub | SySS hub graph (authorities/backbone) | 🟡 PARTIALLY PRESERVED (coordination concept; different topology) | `hub/hub.rs` |
| `Runtime`/`ExecutionContext`/`Executor` | `ExecutionManager` (implements `Gateway`) | 🟡 PARTIALLY PRESERVED | `execution_manager.rs` |
| Debugger/IDE/LSP/CLI | — | 🔴 MISSING | empty dirs |
| `main.py`/REPL | `software/src/main.rs` + bootstrap | 🟡 PARTIALLY PRESERVED (entry exists; REPL/IDE absent) | `bootstrap/`, `src/main.rs` |
| Standard libraries (`libraries/`) | `libraries/` dir (empty at repo root) | 🔴 MISSING | empty |
| Tests | per-crate `tests/` + unit tests | 🟢 PRESERVED (as Rust unit/integration tests) | `software/*/tests/` |

---

## PHASE J — OG CORE RESTORATION MAP

| OG subsystem | OG responsibility | Current New RA component | Impl status | Missing behavior | New RA phase | Evidence |
|---|---|---|---|---|---|---|
| VME `VirtualMachine` | fetch/decode/execute bytecode | (7J.2 ExecutionEngine target) | ❌ not implemented | instruction decode, step loop, StepResult | **7J.2** | `VM`, `DEC` |
| CompilerBackend | AST → `Instruction[]` + pool | `software/compiler/` | ❌ empty | full front-end + backend | later (7L compiler) | `CB` |
| ISA (40 opcodes) | canonical stack ISA | — | ❌ | opcode catalog + decoder | **7J.2** (if REI model frozen) | `INST`/`OPS` |
| RbcWriter/BytecodeReader | binary `.rbc` (RABC) | `ra-persistence` (`.ra` codec only) | 🔴 missing binary codec | binary encoding | deferred | `RW`/`BR` |
| Interpreter `Runtime` | tree-walk AST execution | — | ❌ | — | intentionally NOT in new design | `RT` |
| RMM | RC/PC/SC value store | `ra-memory` | 🟢 implemented | (different design) | 7J.1 done | `MT`/`VMEM` |
| Registry/RID | identity | `ActiveObjectId` | 🟢 implemented | RID format, GMetadata | — | `REG`/`RID` |
| RGC StateTracker | lifecycle authority | backbone Active gate | 🟢 implemented | Ç/Å/⟩/‽/Â/¡ states | — | `ST` |
| GPC LifecycleCoordinator | orchestration | — | ❌ | — | deferred/unused | `LC` |
| EHub | environment coordination | SySS hub graph | 🟢 implemented | environment registry | — | `EH` |
| DB/Sdb engines | structured data | `ra-persistence` LPM/SS | 🟡 partial | Sdb semantics | deferred | `RT` sdb |
| Debugger/IDE/LSP | tooling | empty dirs | ❌ | — | later | — |

---

## PHASE K — DO NOT CONFUSE THESE

1. **OG RA Core** — the Python implementation at `F:\RA assests\Reference\RA.lang`: AST interpreter + VME bytecode VM + GPC/RGC/RMM + EHub. Produces `.rbc` (RABC) binary and Constitution token bytecode. 40-opcode stack ISA.
2. **New RA Core** — the Rust rewrite at `F:\RA_01`: `ra-syss` (hub/backbone/authorities/active objects), `ra-memory`, `ra-persistence`, `ra-gateway`, `ra-runtime`, `ra-bootstrap`. No interpreter, no compiler, no VM yet.
3. **New RA Gateway** — `ra-gateway`: the dependency-free contract boundary (7J) between SySS and the future RA Core.
4. **New RA Runtime** — `ra-runtime`: implements `Gateway` (7J.1); owns `MemoryManager`+`ProgramSpace` via `RuntimeLoader`, `ReiProvider` for pre-lowered REI. No execution yet.
5. **SySS** — `ra-syss`: the platform backbone + storage/persistence/authorities layer; the Gateway is injected additively (`initialize_with_gateway`); SySS never depends on ra-runtime.

**The OG "RC/GPC/PC/RE" acronyms must not be transplanted into the New RA architecture as-is** — OG RMM triples (RC/PC/SC) and New RA `LogicalAddress` memory are different designs; OG GPC/RGC authority stacks map conceptually onto New RA backbone authorities but with a different topology and state model.

---

## PHASE L — CRITICAL QUESTIONS (source-answered)

1. **What exactly was OG RA Core?** A Python language platform: tokenizer → parser → semantic → (a) tree-walking AST interpreter and (b) `CompilerBackend` → 40-opcode stack bytecode → `VirtualMachine`, coordinated by EHub, with GPC/RGC/RMM metadata-memory-lifecycle subsystems. (`MAIN`, `RT`, `CB`, `VM`, `EH`)
2. **What was the OG execution engine?** Two: the `Runtime` AST interpreter (`RT`, 163 KB) — the default; and the `VirtualMachine` fetch-decode-execute engine (`VM`) for compiled `.rbc`.
3. **What was RVM/VME?** `src/rvm/` = package umbrella; `src/rvm/VME/` = the bytecode VM stack: ISA (`INST`/`OPS`), reader/decoder/writer (`BR`/`DEC`/`RW`), stream/stack/frame/constants/registers, and the `VirtualMachine` executor.
4. **What was RMM?** The RA Memory Manager — six name-keyed domains of `MemoryTriple{RC,PC,SC}` (`MT`, `VMEM`), routed by `MemoryRouter` (`MR`). No addresses.
5. **What was EHub?** The Environment Hub — a coordinator-only registry of environments (LE/PE/SE/BE/EE/RE/GPC/RADE/RAPG/RARE), with initialize/shutdown lifecycle (`EH`).
6. **What were RC/GPC/PC/RE?** RC = (a) Runtime slot of MemoryTriple, (b) RcRestorer/RcProgram, (c) Release-Cycle sprint prefix; GPC = Global Program Context (identity/metadata/lifecycle authority stack); PC = (a) Placeholder slot, (b) project/ProgramController via `ProjectExecutor`/`execution_controller`; RE = Runtime Environment (EHub coordinator wrapping `Runtime`).
7. **How did they interact?** `LifecycleCoordinator` orchestrates GPC sub-systems; `MemoryRouter` bridges GPC→RMM; RGC `StateTracker` is lifecycle authority, Registry mirrors it; `VMEAdapter` bridges VME→LifecycleCoordinator; `RbcExecutionAdapter`/`ExecutionContext` bridge restored bytecode→interpreter; EHub coordinates environment lifecycles.
8. **What artifact did the compiler produce?** `(List[Instruction], ConstantPool)` serialized to binary `.rbc` (magic `RABC`, v1.0) via `RbcWriter`; plus the separate Constitution-token `BytecodeEntry[]` text from `BytecodeGenerator`.
9. **How did execution actually begin?** `main.py`: `python main.py script.ra` → tokenize → parse → `Runtime().execute(ast)` (default). Compiled: `CompilerBackend.compile_and_run` or `VMEInstructionRBCAdapter.compile_and_execute` → `VirtualMachine.run()`.
10. **What parts of OG Core are already reconstructed in New RA?** Identity (ActiveObjectId ↔ RID), lifecycle authority concept (backbone Active gate ↔ RGC), coordination (SySS hub ↔ EHub), memory ownership discipline (MemoryManager ↔ RMM ownership rules), platform services (SySS ↔ interpreter service surface).
11. **What is missing?** Interpreter, compiler (all of `src/compiler`+`src/parser`+`src/lexer`+`src/semantic`), VME execution engine, 40-opcode ISA, `.rbc` binary codec, GPC orchestration, debugger/IDE/LSP/CLI tooling, standard library.
12. **Which current 7J work corresponds to OG components?** `ra-gateway` = new boundary (no OG analogue); `ra-runtime` ExecutionManager/RuntimeLoader/ReiProvider = the future VME/loader counterpart (skeleton only); `ra-memory` ProgramSpace/ModuleId = the module-loading side of RMM/bytecode-loading; SySS backbone/authorities = EHub/RGC/Registry roles.
13. **Which current 7J work is NEW architecture rather than OG?** Gateway contract, dependency-injection composition, `LogicalAddress` memory model, backbone hub graph with `ActiveObjectId`, REI concept, pre-lowered-REI loading via `ReiProvider`. None of these exist in OG source.
14. **What must be preserved from OG?** The execution semantics that are frozen and tested: RA truth semantics (`VM._is_truthy`), operand order (right-then-left pops), stack-based evaluation, frame/scope model, CALL/RETURN/branch validation, error classes (stack/opcode/jump/format), output formatting (Yes/No/null), bounded stacks, deterministic streams.
15. **What was intentionally redesigned?** Memory model (triples → LogicalAddress spaces), identity format (RID → ActiveObjectId), lifecycle states (Ç/Å/⟩/‽/Â/¡ → hub lifecycle), coordination topology (EHub envs → backbone authorities), and the entire toolchain (Python interpreter → Rust platform).

---

## PHASE M — SOURCE TRACEABILITY

Every conclusion above cites its source module. Where the OG source provides no evidence: module identity (Phase F), execution identity (Phase F), stop/pause/resume (Phase F), register-based execution (Phase D), and the claimed "43-instruction catalog" / "5B–5F REI architecture" (Phase D — the source defines exactly **40** opcodes and no REI architecture at all) are marked accordingly.

---

## PHASE N — FINAL REPORT

1. **OG RA Core executive summary:** a complete Python language platform with two execution engines (AST interpreter primary; 40-opcode stack VM for compiled `.rbc`), a compiler backend producing `(Instruction[], ConstantPool)` with a documented binary format (RABC v1.0, tagged variable-width operands, little-endian), and a deep metadata/lifecycle/memory authority stack (GPC/RGC/RMM) coordinated by EHub. The bytecode world is secondary and partially bridged — the token-bytecode path restores back to AST.
2. **Complete OG subsystem inventory:** see Phase A table (1,140 files; 20+ subsystems).
3. **OG architecture diagram:** see Phase B/C — three execution paths terminating in (i) AST interpreter, (ii) VME VM, (iii) AST interpreter (restored token path).
4. **OG execution pipeline:** Phase C.
5. **OG instruction architecture:** Phase D — 40 opcodes, variable-width tagged operands, absolute jump addresses, frame/stack model.
6. **OG memory architecture:** Phase E — RC/PC/SC name-keyed triples; no addresses.
7. **OG program/execution lifecycle:** Phase F — synchronous run-to-completion; no stop/pause/resume; RGC lifecycle for entities, not executions.
8. **OG compiler/runtime boundary:** Phase H — `CompilerBackend` (AST→Instructions) ↔ VME; `.rbc` binary artifact.
9. **OG language/runtime mapping:** Phase G table.
10. **OG → New RA mapping:** Phase I.
11. **Missing OG functionality:** interpreter, compiler/front-end, VM execution, ISA, `.rbc` codec, GPC orchestration, tooling (debugger/IDE/LSP/CLI), stdlib.
12. **Intentionally redesigned:** memory model, identity, lifecycle states, coordination topology, toolchain language.
13. **Current 7J status:** 7J (gateway contract) ✅ · 7J.1 (gateway impl + REI-provider load path + SySS injection) ✅ · 7J.2 (ExecutionEngine) **not started** — and per this audit there is **no frozen instruction model in OG source to restore**; the 5B–5F/43-instruction/REI documents referenced in the 7J.2 audit request were **not found in the OG tree** and remain the deciding input.
14. **What should be kept:** the 40-opcode semantics, RA truth semantics, operand order, error classes, bounded-stack discipline, determinism, and the authority-separation pattern (identity/lifecycle/memory authorities).
15. **What should be changed:** nothing in OG source (frozen); in New RA, 7J.2 must decide its instruction model from the 5B–5F REI documents — **not** from OG `.rbc` (which is a different, non-REI encoding).
16. **Recommended next phase:** obtain/confirm the 5B–5F REI architecture documents; reconcile the 40-opcode OG ISA vs the claimed 43-instruction catalog; then implement 7J.2 ExecutionEngine against the frozen REI model.
17. **Exact source files supporting each conclusion:** cited inline throughout (VM, INST, OPS, DEC, BR, RW, CB, FRA, REG, VA, RBCA, BG, RC, REA, EC, EXE, RT, EP, GM, MR, LC, REG, RID, ST, CM, MT, VMEM, EH, MAIN, CLI).
18. **GO / NO-GO for continuing 7J.2:**
    - **GO** to proceed with the parts of 7J.2 that this audit proves are frozen: the execution-model skeleton (session/step abstraction matching the OG `VirtualMachine.run()` loop), operand stack discipline, frame/scope model, branch validation, bounded execution (`max_steps`), truth semantics, and error vocabulary — all directly evidenced in OG source and already present as concepts in the New RA Gateway contract.
    - **NO-GO** to implement an instruction catalog/decoder from OG source alone: the OG ISA (40 opcodes, `.rbc` RABC format) is **not** the REI model the 7J.2 audit request assumes; there is no 43-instruction catalog and no REI/5B–5F architecture anywhere in `F:\RA assests\Reference\RA.lang`. Inventing REI from the OG `.rbc` format would violate the phase's "Do NOT invent" rule.

**FINAL VERDICT:** The OG Core is fully reconstructed and evidenced above. It contains a complete, working, tested 40-opcode stack VM + compiler + interpreter — but **no REI, no 43-instruction catalog, no 5B–5F documents**. 7J.2's instruction model must come from the REI 5B–5F documents (as the corrected audit request states), and this audit confirms the OG source cannot supply them. Everything else required for the 7J.2 execution model (session semantics, frames, stacks, truth rules, error mapping, determinism, teardown) is frozen and documented here with full traceability.
