# Operon backend engine — implementation status and handoff

**Status:** 3.1.0 release preparation, 2026-11-08.\
**Branch:** `fix/3.0.1-installation` (working tree changes, not published).\
**Released scientific baseline:** `c7bd2c6d73c600e899121f335a267c2c64140d94`
(3.0.2 / SDK 3.7).  Transfer-only commits after it do not change the scientific
runtime.\
**Companion documents:** [implementation plan](server_engine_implementation_plan.md),
[architecture proposal](server_engine_next.md), [baseline measurements](server_engine_baseline.md),
[the acceptance record](server_engine_acceptance.md),
[dedicated pool service](pool_service.md), [Linux pool acceptance](pool_linux_acceptance.md),
and [lock order](engine_locking.md).

## Current release follow-up

The implementation handoff below is retained as historical context. Its platform
blocks and test counts describe the earlier coding pass, not the current release
verification. See [current acceptance](server_engine_acceptance.md) for updated
evidence. Release repairs retain ExecutionService in pool mode, account transfer
buffers in the sole pool ledger, probe the selected interpreter identity, validate
optional `resources.cache`, reopen lost pool subscriptions, fail closed on SSH
claim errors, and publish refreshed catalogs atomically to the UI. The default
scheduler and library seed remain unchanged.

## Prior implementation handoff

This document is an honest delivery record.  It distinguishes implemented,
opt-in, simulated and deferred capabilities; a class or a flag is not treated
as proof of end-to-end support.

## 1. Delivered in this change

New package `biopipe/engine/` with transport-independent, tested implementation:

| Module | Responsibility |
| --- | --- |
| `contracts.py` | Frozen plan/resource/attempt/run records, stable error codes, central attempt transition table. |
| `state.py` | SQLite WAL durable repository: schema versioning, one writer, atomic request claim, run/unit/attempt transitions, leases, artifacts/references, events, outbox, coordinator ownership, backup. |
| `events.py` | Durable cursors, bounded pages, snapshot fallback, pull subscriptions. |
| `control.py` | Bounded concurrent framed-request loop: handler/byte admission, absolute deadlines, busy/timeout machine codes, per-connection lifecycle. |
| `resources.py` | Exclusive pool accounting, all-or-nothing leases, pending growth reservation, verified-release-aware ACK. |
| `policy.py` | Pure weighted fairness/ageing, principal share caps, aged large-job reservation, bounded candidate scans, water filling. |
| `facade.py` | Shared engine facade, durable submission journal for adapter-managed jobs, pool identity from the startup snapshot, mode/capability reporting. |
| `coordinator.py` | Single-writer pool coordinator: durable queue, dependency-ready dispatch, launch outbox, cancel, reconciliation, resize polling, epoch ownership. |
| `executor.py` | Executor boundary, process-tree adapter, JobService coordinator adapter; no executor grants resources. |
| `supervisor.py` | Launch receipts, PID+creation-time+boot identity, adoption, confirmed tree stop, quarantine on unverifiable ownership. |
| `environment.py` | Tested mutual-exclusion fallback between repair/install and live attempts; live-orphan/process identity reconciliation. |
| `fs.py` | Engine-owned process-safe file lock and atomic JSON primitive (no UI-server import). |
| `artifacts.py` | Staged outputs, streamed digest verification, fenced immutable publication, explicit crash phases and reconciliation. |
| `retention.py` | Reference-aware mark/sweep, ownership/path checks, quota eviction, partial-failure reporting. |
| `recovery.py` | Restart reconciliation of attempts/leases/artifacts and run settlement. |
| `resume.py` | Incremental input identities, frozen execution identity (presentation stripped), verified cache reuse, fail-closed eligibility. |
| `budget.py` | Revisioned resize proposal/ack, step-boundary worker bridge, conservative process-credit rules. |
| `channels.py` | Byte/block credits, immutable block references, fan-out reference counting, bounded join, group admission. |
| `dag.py` | Topology validation, independent-chain split, readiness, overhead-aware branch decision. |
| `telemetry.py` | Opt-in bounded histograms/counters/gauges, correlation spans, redaction. |

### Product wiring

- `src/web/service.py` opens the engine journal for every `JobService`,
  emits launcher events to the durable event journal, and reports engine state
  through `resources()`.  `BIOPIPE_ENGINE_MODE=coordinator` now performs a real
  drain/inventory, claims the pool, starts a `JobServiceExecutor` and does not
  start the legacy scheduler; `legacy` remains the default.
- `JobService.cancel` no longer waits for a process tree while holding the job
  state lock.  Worker spawn/announce also runs outside that lock; the
  reservation is committed first.  The old public `status == 'cancelled'`
  contract is retained for UI compatibility while `cancel_state` and the lease
  keep it non-terminal for accounting.
- `JobService._dispatch`/`_start` use a dedicated dispatch lock, and a durable
  `cancel_requested` flag closes the admission-to-spawn race.  Coordinator-mode
  starts use the engine lease as the only resource authority and skip the
  legacy admission reservation.
- `EnvironmentGuard` leases every running worker and blocks dependency/plugin
  mutation while any lease is live.  The gate is keyed by the real interpreter
  identity (executable + version + prefix), so different workspaces and
  installation directories using the same interpreter share it; different
  interpreters can repair independently.  This is explicitly a
  mutual-exclusion fallback, not an immutable-generation implementation.
- `HostAdmission.claim_coordinator` is the common ownership gate: inventory and
  claim happen under the admission lock, and legacy `launch`/dispatch/`reserve`
  check the same record.  A scan followed by a later legacy launch is therefore
  refused; older binaries that do not know the record are an explicit
  mixed-version prohibition, not silently tolerated.
- A dedicated `biopipe pool serve` process (the only pool allocator) hosts
  multiple registered `JobService` workspaces through one coordinator.  Every
  run carries its own workspace id, principal, frozen graph/parameters, plugin
  lock and artifact permissions; no process-global mutable working directory is
  used.  Two workspaces and multiple clients submit/query/cancel/reconnect over
  a loopback framed control API (`biopipe.pool_service.PoolClient`), and one
  workspace session can close without cancelling another.
- The workspace-scoped `JobService` coordinator takeover remains available for
  a single workspace, but the multi-workspace path uses the dedicated pool
  service rather than pretending one workspace executor owns the pool.
- Completion now distinguishes `compute_complete`, `artifact_committed`,
  `tree_exited` and `resources_released`/`lease_state`.  A worker descendant
  observed after root exit prevents terminal acknowledgement and keeps the
  lease/reservation charged.
- `ArtifactCommitter.verify_existing` re-hashes existing JobService output
  before any reuse; `commit_existing` is explicitly a verified reference, not
  an assertion that the external payload cannot change.
- The dedicated pool service has explicit session lifetime: `session.open`
  returns a client subscription, `session.close` removes only that session, and
  `workspace.stop` is the separate stop-accepting-work operation.  A workspace
  service is no longer shut down by a client session close.
- The ordinary `Application`/`TaskService` boundary can be configured for the
  pool with `BIOPIPE_POOL_ADDRESS/TOKEN/PRINCIPAL`: launch, submit, details,
  cancel and events go to the pool authority; the application has no local
  HostAdmission, coordinator or scheduler and a pool failure returns
  `engine_unavailable` without a local fallback.  CLI, API, MCP and SSH adapters
  share this boundary.
- `ExecutionService` now has an explicit `execution.cache: "verified"` stage
  cache.  Eligibility is not a hardcoded promise: every operator and reader
  must carry an explicit cache contract, stochastic declarations must bind
  their seed parameters, side effects must be `none`, and the actual dependency
  environment content fingerprint must verify.  Unknown conditions fail closed
  and record reasons in `cache_decisions`.  The mutex/interpreter identity and
  the cache content fingerprint are separate values.
- Bounded channels are exercised inside a real JobService worker process by a
  test-only internal streaming adapter using real `CsvReader` and
  `DescribeStep`; this is wiring evidence, not a production Reader streaming
  claim.
- The dedicated pool service and its Linux acceptance runner are documented in
  [pool_service.md](pool_service.md) and
  [pool_linux_acceptance.md](pool_linux_acceptance.md).

- Catalog refresh replaces the catalog by object identity and increments a
  generation counter; catalog-dependent reads and refresh serialize on the
  existing lock.
- `biopipe/application.py` `TaskService.submit` uses the durable engine request
  claim when enabled.  A definite rollback returns `engine_unavailable`; an
  unknown commit probes and either reuses or returns `submission_uncertain`; it
  never uses the file path as a second launcher.  The per-request file receipt
  remains a compatibility mirror.
- `biopipe/remote/server.py` uses the bounded `ControlLoop`, pins transfer
  leases against timeout cleanup, claims remote `run` identities atomically in
  SQLite, and gates registry refresh / repair with the environment guard.
  `events` and `engine_status` operations are available to newer clients.
- `biopipe/remote/handshake.py` advertises optional engine capabilities
  separately; required base capabilities are unchanged so new clients still
  connect to older servers through documented legacy paths.  History/resources
  are read before the catalog/dependency locks to remove a lock-order inversion.
- `biopipe/control_api.py` and `biopipe/cli.py` expose
  `biopipe engine status` and `biopipe engine events --after ...`.
- `src/task/runner.py` applies pending elastic-budget commands only at task
  boundaries after a successful step.
- `src/web/execution_plan.py` supports opt-in
  `execution.split_independent_branches: true`, splitting linear chains at
  branches/merges while preserving existing default plans byte-for-byte.
- Coordinator-mode completion commits a verified manifest of the final
  JobService output directory through `ArtifactCommitter.commit_existing`; the
  payload is not moved and retention pins it as an external payload.
- The physical pool identity is `capacity domain + control scope`.  Scheduling
  principal, project, client and workspace are not part of it; a different
  `BIOPIPE_ENGINE_PRINCIPAL` cannot obtain a second full-machine pool.

## 2. Module / product / end-to-end status

A passing module test is not evidence that a task package is complete.  The
three dimensions are recorded separately.

| Package | Module implementation | Product integration | End-to-end acceptance |
| --- | --- | --- | --- |
| P00 baseline/observability | Complete: harness, telemetry, bounded metrics | N/A | **Microbenchmark only**; 16-client p95 26.1→5.7 ms. No real SSH/Linux or full-job comparison. |
| P01 contracts/facade | Complete | Facade/journal shared by CLI, API, MCP service and remote; legacy executor remains the default | Local Python service paths; no Linux/remote client matrix |
| P02 durable requests/outbox | Complete incl. commit-outcome classification | `TaskService.submit` and remote `run` claim atomically; file receipt is a mirror, not a fallback launcher | 100-thread claim, crash-after-commit, definite/uncertain failure injection; headless path under stdio shim |
| P03 concurrent control | Complete: bounded handlers/bytes/deadlines; catalog identity replacement | Remote `serve` uses `ControlLoop`; handshake lock inversion removed | Windows loopback only; no real SSH slow-client test |
| P04 durable events | Complete: cursors, retention, snapshot fallback | Remote `events`; `/api/v1/engine/events`; desktop panels still poll | Restart/cursor tests; no desktop UI consumption |
| P05 coordinator takeover | Complete engine coordinator + drain/inventory gate | Single-workspace JobService takeover remains opt-in; the dedicated pool service hosts multiple workspaces under one coordinator and one admission ownership record | **Real two-workspace synthetic worker, multiple control clients, duplicate/disconnect/cancel/restart**, plus a single-workspace real `describe` workflow; real multi-stage Linux/SSH still outstanding |
| P06 fair policy | Complete | Coordinator dispatch; pool clients bind runs to trusted workspace principals; adding connections does not add a principal share | Engine/policy tests + two-client pool test; no untrusted-user isolation claim |
| P07 supervisor/attempts | Complete | Coordinator launches/stops real workers across workspaces; confirmed stop gates lease release; unconfirmed stop becomes `recovery_required` | Windows process-tree tests; no supervisor binary upgrade |
| P08 artifacts/retention | Complete engine artifact/retention implementation | Coordinator commits JobService output manifests; `verify_existing` detects external modification/partial output | Real worker output verified; child-tree alive gate tested at executor boundary |
| P09 resume/cache | Complete policy/artifact verification + descriptor eligibility | Cross-run verified stage cache wired into `ExecutionService`; default off; explicit per-operator/reader declarations, bound randomness, side-effect refusal, environment content fingerprint; input/parameter/artifact/dependency-metadata invalidation | Real ExecutionService/JobService stage cache tests; no live package reinstall test |
| P10 elastic budgets | Complete step-boundary protocol | Worker bridge in `src/task/runner.py`; pending growth reserved | Unit/resize tests; no long real scientific resize run |
| P11 DAG branches | Complete engine DAG/plan split | Opt-in planner split; existing `ExecutionService` parallel stage loop | Engine-level real-process overlap; no full scientific route equivalence |
| P12 bounded channels | Complete credits/fan-out/join/abort | Internal test streaming adapter invoked by a real JobService worker | Test-only adapter; no production Reader declares `memory_modes: stream` |
| P13 streaming acceptance | Complete channel primitives | Real `CsvReader`/`DescribeStep` direct pipeline and real worker adapter | **Partial:** real numeric operator and reader ingestion; not a production streaming Reader/ExecutionService route |
| P14 product integration | N/A | Dedicated pool CLI/control API; ordinary Application/TaskService pool routing; session/workspace/pool lifecycle separated; CLI/API engine diagnostics; headless/Studio tests under shim | Windows local only; real Linux/SSH, MCP, packaging and release remain outstanding |

### What this round changed

- Added a dedicated multi-workspace pool service with a loopback framed control
  API and CLI (`biopipe pool serve/status/submit/cancel`).  The service owns the
  single coordinator and admission domain; each workspace keeps its own job
  directory, frozen parameters, plugin lock and worker cwd.
- Added independent pool sessions and workspace lifecycle.  Closing a client
  session removes only that subscription; another session on the same workspace
  can submit/query/cancel, running work continues, and `workspace.stop` is the
  explicit stop-accepting-work action.
- Added ordinary-application pool routing through `Application`/`TaskService`.
  A client configured with a pool address has no local allocator; desktop,
  CLI, API, MCP and SSH adapters all use the same `launch`/`submit`,
  `details`, `cancel` and `events` boundary.  An unavailable pool returns
  `engine_unavailable` and never starts a local job.
- Cache eligibility now derives from explicit operator/reader cache contracts,
  bound randomness, side-effect declarations and a real environment-content
  fingerprint; missing/unknown declarations fail closed with reasons.  The
  mutex identity remains interpreter-only.
- Environment exclusion now keys on the real interpreter identity, so two
  workspaces/install roots using one interpreter share the gate while different
  interpreter environments can repair independently.  Unconfirmed worker stop
  now becomes `recovery_required` and keeps the lease/reservation.
- Added an atomic admission ownership record; legacy launchers check it before
  launch/dispatch/reserve, closing the inventory-then-launch race for this
  version.  Mixed older binaries are explicitly unsupported.
- Added verified existing-payload artifact checking, lifecycle stage reporting,
  and a real `ExecutionService` stage cache with input/parameter/environment/
  artifact invalidation and explicit cache-contract eligibility.
- Added independent pool session tests: two clients on one workspace, session
  close, reconnect, cancel/query isolation, and explicit workspace stop without
  cancelling running work; and ordinary TaskService launch/submit/query/cancel/
  events routing with no local allocator.
- Added a test-only bounded-channel streaming adapter invoked by a real
  JobService worker; the direct real `CsvReader`/`DescribeStep` fan-out/join
  acceptance remains the scientific evidence, not a production Reader claim.
- `TaskService._submit` no longer falls back to a second submission path when
  the SQLite claim fails.  A definite rollback returns `engine_unavailable`; an
  unknown commit outcome probes the durable request and returns
  `submission_uncertain` without launching; a known existing request is reused.
- The physical pool identity is now `capacity domain + control scope`, not the
  scheduling principal, workspace or client label.  `PoolSpec.principal` is the
  OS pool owner; `EngineRuntime.principal` is the fairness identity.
- Handshake no longer holds handshake/dependency locks while taking the
  job-state lock.  The new order is documented in
  [engine_locking.md](engine_locking.md).
- `EnvironmentGuard` provides a tested mutual-exclusion fallback (not
  generations): a repair/install blocks new workers and waits for zero live
  attempt leases; a running job blocks repair; a live orphan worker keeps the
  exclusion after its launcher dies.
- Coordinator mode now performs drain/inventory, claims exclusive ownership,
  starts the coordinator thread, refuses dirty legacy queue/reservations/other
  live launchers, dispatches real JobService workers (including a real
  `describe` workflow), releases leases after confirmed exit, commits
  job-output manifests, and supports public cancel and restart adoption.  The
  legacy scheduler is not started in this mode.
- Added a real streaming numeric acceptance pipeline: `CsvReader` loads a
  table, two `DescribeStep` streaming branches consume a fan-out of owned
  chunks, a join compares both results with serial `describe`, and tests cover
  slow consumers, failure/abort, duplicate ACKs and borrowed-buffer copying.
- Added a product-path `ExecutionService` retry test: a completed stage is not
  re-executed when the failed remaining stage is retried.  Cross-run cache
  lookup is still not wired; the engine planner remains module-level.

## 3. Decisions taken where design and code conflicted

1. **Public cancel status vs. terminal cancellation.**
   Existing desktop/UI tests assert that a running job reports `cancelled`
   immediately.  The engine therefore keeps that public status for
   compatibility, adds `cancel_state` (`requesting`/`stopping`/`stopped`) and
   retains the lease until the supervisor confirms the tree is gone.  This is
   a deliberate adapter-level compromise, not a claim that the process stopped
   when the status changed.

2. **Engine journal vs. existing file receipts.**
   `TaskService` already had working durable per-key file receipts.  With the
   engine enabled, the SQLite claim is the sole acceptance authority and the
   file receipt is a compatibility mirror.  If the claim definitely rolls back,
   submission returns `engine_unavailable` without launching; if the commit
   outcome is unknown, it probes and either reuses the durable request or
   returns `submission_uncertain`.  It does **not** fall back to the legacy file
   submission path while the engine is enabled.  Only `BIOPIPE_ENGINE_DISABLE`
   selects the file-only path.

3. **Process credits are not reclaimed by managed shrink.**
   The conservative implementation follows the plan: a successful
   `MemoryRuntime.update_budget` never proves native RSS release.  Shrink ACKs
   keep process credits charged unless an injected, separately tested release
   verifier succeeds; normal reclaim occurs at confirmed process exit.

4. **Coordinator takeover is real and explicit.**
   Single-workspace `BIOPIPE_ENGINE_MODE=coordinator` still performs a real
   takeover, but true multi-workspace operation uses the dedicated
   `biopipe pool serve` process.  Both claim the admission ownership record,
   refuse dirty legacy state, and never start the legacy scheduler beside an
   active coordinator.  The default remains `legacy`.
5. **Pool ownership is atomic, not scan-based.**
   `HostAdmission.claim_coordinator` inventories and claims under the admission
   lock.  New-version legacy launchers check the same record before launch,
   dispatch and reserve, so a request that passed an earlier scan cannot become
   a second allocator.  Older binaries that do not honor the record must not run
   concurrently; this is a deployment prohibition, not a silent compatibility
   claim.

6. **Remote handshake compatibility.**
   Engine capabilities are advertised separately from the required base
   capabilities.  Older servers are still accepted; newer features fail with a
   capability error rather than a broken connection.

7. **Windows process termination.**
   The DSH sandbox denies `suspend()`/`resume()` rights.  The supervisor stops
   an owned tree by enumerating descendants, terminating them and the root,
   waiting for confirmation, with an explicit `taskkill` fallback.  Permission
   failures raise `stop_unconfirmed` and keep the lease charged instead of
   pretending resources were released.

8. **Environment generation fallback.**
   Immutable generations are not implemented yet.  `EnvironmentGuard` is a
   mutual-exclusion scheme keyed by the real interpreter identity: a
   repair/install holds an exclusive marker for that environment and requires
   zero live attempt leases in it; a new worker for that environment refuses to
   start while the marker is held.  Workspaces sharing one interpreter share the
   domain; distinct interpreter/prefix environments can proceed independently.
   This prevents in-place mutation under a running worker but gives no rollback,
   no two-generation parallelism and no protection from an out-of-band
   administrator changing files.  It is explicitly marked as a fallback.

9. **Physical capacity vs. fairness identity.**
   `capacity_domain` is host + OS account (+ uid) and the engine control scope;
   `PoolSpec.principal` is the OS pool owner.  `BIOPIPE_ENGINE_PRINCIPAL` only
   changes the scheduling/fairness identity of runs, so it cannot create a
   second full-machine pool.  A workspace, client or project is never part of
   the physical pool identity.

10. **Lock order is proven, not assumed.**
   The handshake read path now takes job-state snapshots before its
   catalog/dependency locks; the environment gate is ordered after job state
   and is not taken by repair while a job lock is held.  See
   [engine_locking.md](engine_locking.md) for the component DAG and the
   remaining constraints.

## 4. Test evidence

All commands below were run from the worktree root with the project virtual
environment.  The local sandbox required a workspace-local pytest temp root and
a test-only `os.mkdir` mode shim; neither is shipped.

### New engine and integration suites

```powershell
python -m pytest tests/test_engine_state.py tests/test_engine_idempotency.py `
  tests/test_control_limits.py tests/test_engine_artifact_commit.py `
  tests/test_engine_artifact_existing.py `
  tests/test_engine_retention.py tests/test_engine_resume.py `
  tests/test_engine_resize.py tests/test_engine_channels.py `
  tests/test_engine_attempts.py tests/test_engine_pool.py `
  tests/test_engine_dag.py tests/test_engine_policy.py `
  tests/test_engine_telemetry.py tests/test_application_engine_requests.py `
  tests/test_remote_concurrency.py tests/test_engine_api.py `
  tests/test_engine_shadow.py tests/test_engine_catalog_generation.py `
  tests/test_engine_shared_pool.py tests/test_engine_environment_gate.py `
  tests/test_coordinator_job_service.py tests/test_engine_stream_graph.py `
  tests/test_engine_stream_execution.py tests/test_execution_resume_product.py `
  tests/test_execution_cache.py tests/test_pool_service.py tests/test_pool_cli.py `
  tests/test_unified_pool_entry.py -q
```

**Result: 140 passed, 2 warnings, 0 failed** (~231 s) on Python 3.12.14 /
Windows 11.

Highlights:

- Dedicated pool service hosts two workspaces and multiple control clients with
  real workers in their own cwd; duplicate request one run/attempt; disconnect
  and workspace-session close do not cancel; cancel A leaves B running; restart
  adopts one live worker; environment repair in B blocked while A runs;
  injected submission failure leaves no run/lease and the pool recovers.
  Injected artifact-publication failure reports compute complete + artifact
  false + tree exited + resources released as separate states.
- Cross-run cache hit reuses a verified child without a new worker; changed
  input, changed parameter and damaged artifact miss and create a new worker;
  opting out disables the cache.
- Existing-payload artifact verification detects changed/additional/missing
  files; executor refuses terminal state while a worker tree is alive.
- A test-only streaming adapter uses bounded channels inside a real JobService
  worker, with real CsvReader and DescribeStep.
- All prior engine/coordinator/stream/direct tests remain green.

- 100 concurrent identical submissions → one durable run, one outbox identity,
  one launch; different content under the same key → `idempotency_conflict`.
- Commit-outcome-unknown probes and never relaunches; definite rollback returns
  `engine_unavailable`; unavailable request evidence returns
  `submission_uncertain`; recovery reuses the durable request.
- Real process trees: launch receipt replay adopts, stale fence is rejected, the
  owned child is confirmed dead before release, unconfirmed stop becomes
  `recovery_required` with the lease retained.
- Dedicated pool and single-workspace coordinator tests cover real workers,
  cancellation, restart adoption, public details and durable lifecycle fields.
- Cross-run verified cache: hit creates no new worker; input/parameter/artifact
  damage invalidates; opt-out disables.
- Real streaming numeric pipeline and real-worker test adapter cover channel
  backpressure, abort, duplicate ACK and buffer copying.
- Artifact crash points and existing-payload corruption are detected; slow
  request isolation, slow-drip deadline and handler saturation remain green.


### Real environment gate (not passed)

The handoff gateway was TCP-reachable on 2026-11-08, but the recorded Linux
instance was `shutdowned`; starting it is a paid provider action not authorized
in this task.  A passwordless SSH attempt reached the gateway and was denied
because the prior workflow used an interactive password that is not persisted
in the checkout or profile.  No credentials were written, no instance was
started, no private data was uploaded, and the Linux/SSH matrix remains
**not passed**.  The executable runner and checklist are in
[pool_linux_acceptance.md](pool_linux_acceptance.md); the blocker evidence is
`docs/design/evidence/pool_linux_not_run_2026-11-08.json`.

### Existing regressions run

```powershell
python -m pytest tests/test_contracts.py tests/test_execution_plan.py `
  tests/test_job_admission.py tests/test_readiness.py `
  tests/test_memory_runtime.py tests/test_storage_runtime.py `
  tests/test_execution_api.py tests/test_execution_progress.py `
  tests/test_server_cli.py tests/test_application_library_separation.py -q
```

**Result: 145 passed, 1 failed, 1 teardown error.**  The single failing test is
`test_persistent_unmanaged_pressure_is_contained_and_logged`, which also failed
on the released baseline before any engine change; its worker-pressure watcher
exercises `psutil` suspension that the DSH sandbox denies.  A wider earlier run
of 16 suites (including the SSH execution-service suites) produced 193 passed,
22 failed and 9 errors; every observed failure falls into the environment
categories below, not a claim that all desktop acceptance passed:

- dependency probes report `(pid=...)` because the sandbox denies the piped
  subprocess path used by `owned_process`; headless/route/readiness suites that
  require a live probe are blocked;
- `psutil.Process.resume()` is denied by the sandbox (`AccessDenied`), affecting
  `test_isolation`, `test_bytecode_cancel`, one Studio cancel test and the
  persistent-pressure case;
- remote tests require a real Linux/SSH peer.

With a test-only file-stdio shim for dependency probes, the complete
`tests/test_headless_application.py`, `tests/test_studio.py` and
`tests/test_engine_api.py` ran **19 passed, 2 failed**.  The first failure is
the child CLI process not inheriting the test shim (the parent-process
submission/idempotency tests pass); the second is the Studio test itself calling
`psutil.Process.suspend()`, which the sandbox denies.
`tests/test_agent_transports.py` fails at the sandbox's named-pipe creation
(Windows `PermissionError`), so MCP transport acceptance is not claimed.
Remote handshake/transfer/protocol suites: **56 passed, 1 skipped**.  No
regression attributable to the engine changes was identified in the runnable
portions; the remaining acceptance requires the platform-specific environments
listed in the plan.

### Performance

Measured in `docs/design/server_engine_baseline.md`: 16 clients, one 400 ms
slow request, 320 status samples per mode.  Baseline p95 **26.1 ms**, p99
**401.6 ms**; bounded concurrent loop p95 **5.7 ms**, p99 **26.6 ms**.  This is
a **control-loop microbenchmark** on one Windows machine, not a full
application speed-up: it excludes SSH, real network RTT, dependency probing,
worker startup and scientific computation.  No overall application speed-up is
claimed; the real SSH/Linux matrix remains unmeasured.

## 5. Configuration

New optional environment/configuration inputs:

| Setting | Default | Meaning |
| --- | --- | --- |
| `BIOPIPE_ENGINE_MODE` | `legacy` | `legacy`, `shadow`, `coordinator`.  `coordinator` drains/inventories and starts the real coordinator; it fails explicitly when legacy state or another launcher is present.  Default remains legacy until acceptance decides |
| `BIOPIPE_ENGINE_DIR` | `<admission-dir>/engine` | Control database location; shared by all workspaces in the same authorized pool, independent of a workspace path, and must be local (not NFS) |
| `BIOPIPE_ENGINE_PRINCIPAL` | OS user | Scheduling/fairness identity only; it does not change the physical pool owner or capacity |
| `BIOPIPE_ENGINE_METRICS` | off | Enable local histograms/counters |
| `BIOPIPE_ENGINE_DISABLE` | off | Disable the engine journal and coordinator entirely (emergency rollback to the legacy file path) |
| `BIOPIPE_ENVIRONMENT_GATE` | `<admission-dir>/../environment-gate.json` | Interpreter-identity mutual-exclusion marker shared by repair/install and running attempts |
| `BIOPIPE_POOL_TOKEN` | none | Local pool control token; `pool serve --config` can generate `<root>/pool-token` instead |
| `BIOPIPE_CONTROL_HANDLERS` | 32 | Bounded control handlers |
| `BIOPIPE_CONTROL_FRAME_BYTES` | 128 MiB | Per-frame maximum |
| `BIOPIPE_CONTROL_INFLIGHT_BYTES` | 512 MiB | Aggregate body-byte admission |
| `BIOPIPE_CONTROL_INACTIVITY` / `BIOPIPE_CONTROL_DEADLINE` | 30 s / 120 s | Inactivity and absolute request deadlines |

The pool ceiling is frozen from the existing `HostAdmission` startup snapshot
(90% of detected available memory by default).  The engine never rescans free
memory to redefine it; pending-growth reservations are included in committed
usage until an ACK or rejection.  The physical pool identity is capacity domain
(host + OS account) plus control scope.  Scheduling principal, project, client
and workspace are fairness dimensions only; none can create a second pool or
extra capacity.

## 6. Migration and rollback

- The engine database is created beside the existing data directory; existing
  `job.json` records remain readable and authoritative for legacy work.  No
  old job or frozen parameter file is rewritten.
- Rollback for local work: set `BIOPIPE_ENGINE_DISABLE=1` (or remove the engine
  directory after backing it up) and restart the service.  The existing file
  receipts and job directories continue to work.  Do not downgrade a live
  coordinator lease database; drain and stop owned workers first.
- Newer schema versions are refused explicitly; the database is never silently
  recreated.  A backup can be produced through `StateStore.backup()`.
- Request-key reuse with different content is a conflict; receipts are durable
  but not promised to be retained indefinitely (event retention is bounded).

## 7. Remaining work / handoff

Highest-value next steps, in dependency order:

1. **Environment generations (P03/P04):** replace `EnvironmentGuard` mutual
   exclusion with immutable, verified environment generations (new generation
   for install/repair; existing tasks keep the old one; reference-aware cleanup).
   Until then, the only guarantee is interpreter-identity exclusion; there is
   no rollback and no concurrent old/new generation.
2. **Extended Linux operations:** the 3.1.0 pass completed two-client SSH,
   installed-wheel numeric execution, cancellation, reconnect and real pool
   CLI process crash/adoption. Systemd integration, long WAN impairment and
   real disk exhaustion remain operational follow-ups. See current acceptance.
3. **Trusted-principal authentication and multi-user boundary:** the pool's
   principal is configured by the operator and the token is local access
   control.  A claim of isolation between untrusted OS users is explicitly out
   of scope; use separate OS accounts/hosts until a real authentication and
   filesystem boundary exists.
4. **Full scientific coordinator acceptance (P05/P08/P11):** run a real
   multi-stage workflow under the dedicated pool, compare outputs/metadata with
   legacy execution, exercise failed-stage retry, cache reuse and long-job
   fairness.  The release pass adds an installed-wheel Reader/scale route, actual array
   equivalence, stage reuse and crash recovery; large scientific workloads and
   sustained fairness performance remain to be measured.
5. **Product streaming integration (P13):** no existing Reader declares
   `memory_modes: stream`.  The internal adapter proves channel wiring in a real
   worker, but a production path needs an explicit streaming Reader/operator
   capability and route comparison.  Prepare the separate library-side
   interface list rather than changing `library/`.
6. **Desktop/package gate:** only if host/UI/packaging paths change; rebuild the
   exact candidate and run Setup/shortcut acceptance.  The release pass verifies real MCP stdio without shims; fresh test-PC
   Setup/shortcut acceptance remains separately scoped.


Known unimplemented boundaries (explicit, not hidden):

- no immutable environment generations; only interpreter-identity mutual
  exclusion, with no rollback and no concurrent old/new generation;
- the pool token/principal is local access control, not authentication between
  untrusted OS users; use separate accounts/hosts for that boundary;
- no cross-run cache reuse unless the graph explicitly sets
  `execution.cache: "verified"`; implementation/package identity is recorded but
  a live package reinstall test is not available;
- no arbitrary process-memory checkpoint/resume;
- no hard RSS enforcement without supported OS mechanisms;
- no live-worker adoption across incompatible supervisor binaries;
- no GPU sharing, Slurm/Kubernetes executor or Tauri host;
- no automatic migration from live legacy binaries; drain before upgrading;
- no existing Reader declares streaming (`memory_modes: stream`), so P13's
  worker adapter is test-only and not a production Reader/ExecutionService
  route;
- no real Linux/SSH multi-client, MCP named-pipe, or packaging acceptance in
  this window.

## 8. Files changed (summary)

New: `biopipe/engine/*` (21 modules), `biopipe/pool_service.py`,
`scripts/benchmarks/control_plane.py`, `scripts/acceptance/*`,
`tests/test_engine_*.py`, `tests/test_control_limits.py`,
`tests/test_remote_concurrency.py`, `tests/test_application_engine_requests.py`,
`tests/test_engine_api.py`, `tests/test_coordinator_job_service.py`,
`tests/test_engine_stream_graph.py`, `tests/test_engine_stream_execution.py`,
`tests/test_engine_environment_gate.py`, `tests/test_engine_artifact_existing.py`,
`tests/test_pool_service.py`, `tests/test_pool_cli.py`,
`tests/test_execution_cache.py`, `tests/test_execution_resume_product.py`,
`tests/test_unified_pool_entry.py`, `docs/design/server_engine_baseline.md`,
`docs/design/server_engine_acceptance.md`, `docs/design/pool_service.md`,
`docs/design/pool_linux_acceptance.md`, `docs/design/engine_locking.md`,
this document, evidence JSON.

Modified: `src/web/service.py`, `src/web/execution.py`,
`src/web/execution_plan.py`, `src/web/admission.py`, `biopipe/application.py`,
`biopipe/cli.py`, `biopipe/readiness.py`,
`biopipe/remote/server.py`, `biopipe/remote/handshake.py`,
`biopipe/remote/client.py`, `biopipe/control_api.py`,
`src/task/runner.py`, `tests/test_execution_plan.py`,
`tests/test_job_admission.py`, `docs/README.md`, `docs/agent_operations.md`,
`docs/V3_IMPLEMENTATION.md`.

No library seed, scientific operator, frozen parameter JSON, version number or
published artifact was modified.
