# Automatic canvas RunPlan preparation

Status: development on `feature/canvas-runplan`, based on Operon 5.2.0. No
application version, release asset or library source changed. This is a tested
native-route integration, **not complete automatic export coverage of every
existing operator or execution topology**.

## Product flow

The original canvas Run button and File > Export standalone bundle now enter
`Application.canvas_plans`. Both freeze the graph before preparation and use
the same compiled RunPlan, code snapshot, environment generation and input
bindings. The existing advanced Plan panel remains available.

1. Prepare saved values and validate the selected execution environment.
2. Respect the existing placement result. A single selected remote host is
   handled on that host; mixed-host plans are rejected instead of run locally.
3. Compile through `Application.compile_plan` / `WorkflowCompiler`. Expanded
   routes, converters and script values use the existing compiler.
4. Capture the selected private CPython runtime and installed dependencies once.
   Separate dependency targets remain separate; conflicting targets retain the
   existing subprocess adapter. Declared private interpreter environments can
   also be captured without merging them into shared dependencies.
5. Collect the execution kernel and selected provider namespaces, including
   package data. Generate implementation manifests automatically. Declared
   parameter/Reader resources become fingerprinted package-relative references.
6. Save the prepared body before any scientific submission. Run uses PlanService
   and the existing pool; Export uses PlanExportService and the existing exporter.

No provider is imported to discover files. Code hashes must match the frozen
descriptor. Package resources outside a namespace must be declared through
`x-operon-path`; a string that resembles a filename is not sufficient evidence.
File data are streamed during copying/hashing, not materialized as a matrix.

## Runtime and package ownership

Preparation is explicit user-requested work, not app startup, registry refresh
or a new dependency installer. The environment gate protects the source runtime
while it is captured. Actual execution leases the immutable captured generation.
Later preparations reuse package receipts; they do not walk all expanded
dependency files again. Kernel code identity is included in the prepared plan
to avoid reusing an older kernel after application code changes.

The native worker still runs `src.task.Context` and its existing runner. Managed
memory, process reservation, spill, Reader disk access, streaming, logs and
independent parameter JSON are not replaced by a second execution engine.
Transport buffers use the existing admission service. Server result files are
resolved by owned run/artifact/file identifiers before a verified transfer.

User input datasets remain external input bindings in the standalone package's
`inputs.json`; they are not silently duplicated into an offline bundle. Edit
those paths when moving the package to another data location. Code, declared
resources, frozen parameters and the supported runtime are included. An exported
launcher does not connect back to an Operon desktop or service.

## API and durable operations

All routes are under `/api/v1/canvas-plans`:

| Operation | Permission | Request |
|---|---|---|
| POST `prepare` | run | `{graph, request_id}`; returns a preparation receipt immediately |
| GET `status` | context | `request_id` |
| POST `cancel` | run | `{request_id}`; cancels preparation, not a submitted workflow |
| POST `execute` | run | `{preparation_id, request_id, action: "run" | "export", output?: string}` |
| GET `history` | context | Latest 100 action receipts |
| GET `outcome` | context | `request_id`; queries the authoritative plan/export owner |

Preparation probes execute runtimes, so edit/context permission alone cannot
start preparation. A client retries the same submission body with the same ID
after a lost response. Reusing an ID for different content is an error. A crashed
preparation owner becomes an interrupted receipt, never an implicit resubmission.
The preparation queue is bounded to one active and one waiting request.

SSH exposes the same server Application through `canvas.*` and allowlisted
`plan.read` operations. A capability check precedes data upload. Resumable file
transfer and companion-file discovery reuse the existing transport. Closing a
window does not cancel an accepted pool run. A server with active preparation or
export work cannot be retired as idle.

## Explicit coverage boundaries

- Private CPython prefixes and venv packages are captured separately. System
  Python acquires an exact-patch standalone CPython bootstrap. Conda captures
  its scientific prefix with conda-pack and uses a separate private management
  bootstrap. No installation mutates the selected scientific environment.
- Declared tools in Conda prefixes, self-contained private tool installations,
  private R runtimes and prepared R package libraries are collected automatically.
  System R acquires an exact-version managed R runtime. A tool whose resources
  lie outside a known prefix is rejected with a preparation error; an executable
  alone does not prove its dynamic libraries or data files are portable.
- C/C++ temporary scripts use their declared compiler toolchain; that compiler
  must have a portable closure. Arbitrary `/usr/bin/cc` is not silently copied.
- A graph assigned to multiple execution hosts requires multi-unit host/storage
  lowering. The native-chain automatic entry currently rejects it. It does not
  silently override per-node placement or downgrade to the legacy scheduler.
- Nested route reference-file upload needs further integration. Ordinary native
  route expansion works; do not assume every nested remote reference is staged.
- Dedicated private-interpreter capture is implemented but has not received a
  real packed-interpreter end-to-end acceptance in this change. Ordinary conflict
  target subprocess execution has.
- Arbitrary external files opened dynamically by author code cannot be inferred
  reliably. Such dependencies must be declared; no library declarations were
  changed or fabricated by this work.
- Existing headless legacy TaskService calls remain compatible. They have not
  all been redirected to this new automatic preparation API.

Because of these boundaries this branch is not a universal replacement for
every original multi-host Run configuration. Release requires the platform
acceptance gates; module tests alone do not satisfy them.

## Targeted evidence (2026-11-15)

- Initial adapters/native snapshot/plan/export tests: 45 passed, one opt-in
  runtime test skipped in that unit-test command.
- Updated canvas/native/server/service group: 35 passed, two failures corrected
  in subsequent focused checks, one opt-in runtime skip. Placement correction
  passed separately; isolation binding, HTTP permission and new server dispatch/
  liveness checks subsequently passed (4 checks).
- Package/isolation/disk Reader/bridge regression selection: 8 passed; two tests'
  own plain-path fixture operations exceeded Windows path limits. Those exact
  two passed in a fresh short temporary directory. Product long-path execution
  was tested separately, not inferred from the short fixture.
- Frontend TypeScript/Vite build passed; plan state/API tests: 7 passed.
- Real private Python preparation, package reuse without resealing, pool native
  execution and artifact production passed. Readiness was an explicit fixture;
  this is not a desktop readiness acceptance claim.
- A generated standalone package was moved to another deep directory. With
  developer `PYTHON*`, `OPERON*` and `BIOPIPE*` variables removed, its own launcher
  completed the route using its own interpreter, exit code 0.
- A real frozen-target isolated subprocess invocation completed under the same
  pool and preserved the 32 MiB managed budget / 192 MiB process reservation.

Evidence lives under `verification/backend/`: XML reports, automatic export
receipts, `standalone-final.json`, `isolation-actual.json`, and the focused
`canvas_isolation_check.py` reproduction. Intermediate failed diagnostics are
retained. These initial integration checks preceded the real Linux and installed
desktop gates below; they did not include a full scientific-suite rerun.

## Automatic closure acceptance (2026-11-15)

The subsequent 5.3.0 change captures Conda/system-Python/R/tool closures. Windows
private Python plus actual R computation, moved standalone execution with spaces,
and owned R scratch cleanup passed. Linux system-Python-derived and Conda 3.13
routes completed preparation, reuse, pool execution and independent moved export;
the Conda fixture also executed the real xz compression/decompression tool.
Linux monitor initialization/cancellation/fencing tests passed (5 tests). Official
runtime archives were supplied through a local mirror after the server download
stalled; this is not evidence that the original online download completed.

Focused checks: 17 passed for R/path/closure execution, 38 passed and one opt-in
skip for canvas/package/native/R/SSH regressions, and 8 final closure selection
checks passed. The opt-in runtime was exercised separately. A broader portability
selection returned 31 passes and 5 failures. The same five failures reproduce
on 5.2.0: audit matches historical example paths, old copied-code fixtures omit
the independent Reader library, and legacy history rebasing fails. These are not
reported as passed or as caused by the new export path. No library was changed.

Final Setup interaction and exact server-archive installation are separate gates;
see the release acceptance record rather than inferring them from these tests.

## Tauri handoff

Read [module inventory](tauri_module_inventory.md),
[implementation contract](tauri_implementation_contract.md), and
[coding instructions](tauri_coding_instructions.md). Tauri is a separate future
experimental shell branch, not an alternative scheduler or compiler. It must not
hide the automatic-export coverage boundaries above.
