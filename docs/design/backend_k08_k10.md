# K08-K10 cluster foundation implementation checkpoint

Date: 2026-11-14. This is an implementation handoff, **not acceptance of K08,
K09, or K10**. The normative source is
[backend_implementation_contract.md](backend_implementation_contract.md).
The initial ownership was expanded to include host pool RPC hooks and an
administrative cluster CLI. Application/HTTP/MCP plan wiring has a separate
integration owner.

| Unit | Implemented behavior | Module tests | Product integration | Real E2E | Remaining blockers |
| --- | --- | --- | --- | --- | --- |
| K08 | PostgreSQL 17 repository, migrations, quotas, outbox, dedicated leadership session, persistent controller | Written; not run in this delegated development phase | Service hooks only | Not run | Qualified pinned extras; real database fault/concurrency execution; endpoint/auth wiring; retention/watermark policy integration |
| K09 | Bounded placement, SSH receipt client, same-host same-key recovery, durable cancel intent, host StateStore epoch guard and RPCs | Written; not run | Host hooks implemented, not executed | Not run | Two independent compute hosts; real disconnect/restart/surviving-worker evidence |
| K10 | Real Slurm CLI adapter, token reconciliation, owned cancellation, direct allocation worker | Written; not run | Requires prepared package, site profile and output collector | Not run | Actual scheduler/accounting access; site capability and requeue-policy probe; pending/run/cancel/accounting-delay acceptance |

No library files, application versions, release artifacts, or published refs are
changed by this patch. Static AST parsing covered 28 new/modified Python files
without running tests. Static parsing is not import, database, runtime, or
integration evidence.

## Ownership and concurrency

`operon.cluster` has no startup side effects and does not import psycopg until
`Postgres` is constructed. PostgreSQL remains an explicitly provisioned service
extra. `DatabaseConfig` enforces PostgreSQL major version 17 and a named schema;
the schema must already exist. Do not place secrets in inventory, plans,
storage topology, or dispatch payloads. The DSN stays in service configuration.

There are six ordinary DB connections, one scheduler connection, one lifecycle
connection, and a separate session that owns the leadership advisory lock.
Connections have finite connect, acquisition, statement and lock timeouts.
`BoundedExecutor` acquires a semaphore before queueing work. The shared DB
executor has the same 6/1/1 lanes. SSH work has six dispatch slots, one polling
slot, and one reserved cancellation slot. One scheduler thread runs at a time.
The controller and service must share their DB executor; constructing
`ClusterService(repository, controller=controller)` does this automatically.

Migrations are packaged numbered SQL with SHA-256 checksums, installed under an
exclusive transaction advisory lock. Changed checksums or an unknown newer
migration fail closed. There is no destructive downgrade. All runtime values
use psycopg parameters; only packaged SQL migrations are executed as SQL text.

The lock order for existing records is controller epoch, run, placement/unit,
then quota. Submission serializes the request key, resolves replay first, then
locks its principal quota row and inserts new records atomically. Network,
process, environment build, and staging operations are outside transactions.
Deadlock/serialization retry contains only a pure SQL callback. An uncertain
commit raises `commit_outcome_unknown` and requires lookup of the original key.

Leadership acquisition increments a durable epoch. After reacquisition,
previously dispatching commands become unknown. Each prior active command is
reconciled before new dispatch is enabled. Unknown attempts retain the same
node, key, and ownership; uncertainty never enables replacement submission.
Losing the leadership connection stops further dispatch, not remote workers.

## Integration API

Core constructors:

```python
database = Postgres(DatabaseConfig(dsn, schema="public"))
database.migrate()
repository = ClusterRepository(database, limits=AdmissionLimits(...))
leadership = Leadership(database, cluster_id="stable-cluster", owner_id="process-instance")
planner = PlacementPlanner(controller_id="authenticated-controller", prepared=prepared_bindings)
controller = ClusterController(repository, leadership,
    executors={"ssh": ssh_executor, "slurm": slurm_executor}, planner=planner)
service = ClusterService(repository, controller=controller)
```

Start `controller.start()` explicitly in the persistent server lifecycle, after
configuration/capability validation. `service.close()` stops owned controller
work; it does not cancel scientific jobs. Close `database` afterward.

`ClusterService` provides async `submit(principal, request_id, plan,
preparations=0)`, `lookup(principal, request_id)`, `status(principal, run_id)`,
`cancel(principal, run_id)`, and `events(principal, after="0", limit=200)`.
Arguments are keyword-only. The adapter must resolve an authenticated principal
before invoking these hooks. The plan is the existing strict `RunPlan`; its
computed identity must match before admission. Durable event cursors and
revisions are decimal strings on the wire.

Repository methods additionally expose:

- `register_node`, `heartbeat`, `register_storage`, `register_mount`, and
  `bind_environment` for verified inventory/bindings.
- `ready(limit<=256)`, `prepare_dispatch`, `claim_dispatch`, `dispatches`,
  `recovery_barrier`, `observe`, `cancellations`, and `finish_cancel` for control.
- `update_cost` for persistent EWMA samples/count/confidence.

Registration's `capacity_domain` must come from authenticated physical pool
inventory, never an SSH alias or account name. The unique database constraint
rejects two aliases for the same domain. An administrator may name independent
partitions only after verifying their enforced cgroup/VM boundary.

`PreparedBinding(payload_json, binding_id)` is indexed by `(run_id, unit_id,
node_id)` in `PlacementPlanner.prepared`. The producer must complete environment
verification and required transfers before making a binding available. The
planner never builds environments or performs remote I/O. Missing bindings are
not dispatched. `binding_id`, when supplied, must reference a verified generation
on the selected node. This hook is the remaining connection to K03/K07/K11.
The explicit controller CLI can now load these preparations from checksum-bound
deployment files; automatic application preparation/staging remains separate.

`plan_placements` filters OS/architecture/Python ABI, executor, capability,
environment, device, reachable storage, route affinity, explicit node and health.
It uses fair principal rounds, age and stable IDs, at most 256 units/four ranked
nodes, and 50 ms planning CPU work. Explanations expose each ineligible reason
and every conservative default used for unknown costs. Hosts still decide RAM
and CPU grants. Admission rejection does not spend a scientific retry; this
checkpoint does not automatically retry scientific failures. The controller
persists one candidate dispatch per unit per pass. Further candidates are
available to an integration policy after proved non-acceptance; no unknown
submission is eligible for this fallback.

## Host fence and request receipt hook

`SSHPoolExecutor(lease, controller_epoch=callable,
expected_host_identity=callable)` uses an existing framed transport. `lease`
is a context manager factory `(node_id, lane)` returning a uniquely leased
`SSHConnection` (`call`) or tunneled `PoolClient` (`request`). The connection
must negotiate `cluster.controller_fence.v1`. Missing capability fails closed;
the adapter never falls back to unfenced legacy submission.

Required methods are `cluster.submit`, `cluster.lookup`, and `cluster.cancel`.
All carry these fields:

```text
controller_id, controller_epoch, request_key, command_id,
cluster_run_id, cluster_unit_id, cluster_attempt_id, workspace, principal
```

`submit` additionally carries the frozen `graph`. `cancel` additionally carries
the persisted `host_run_id`, `host_fence`, and bounded `timeout_seconds`.
`lookup` is read/reconciliation only and must never launch a job. An optional
`cluster.status` can use the same receipt contract, but the client uses lookup.

`PoolControlServer(controller_id=...)`, or the host administrator's
`OPERON_CLUSTER_CONTROLLER_ID`, binds one controller identity to that endpoint's
existing authenticated token. The SSH bridge additionally restricts workspace
and principal to its registered OS-account workspace. Without this explicit
configuration the capability is not advertised. The host persists
its highest accepted `controller_epoch` and rejects stale mutating commands.
Do not trust a caller's unauthenticated identity field. An epoch is a controller
fence; it must not replace or reset the host pool's resource fence. Higher
epochs can reconcile older owned attempts. They cannot duplicate or terminate
unowned attempts.

An accepted response contains:

```text
request_key, command_id, cluster_attempt_id, host_identity,
host_run_id, host_attempt_id, host_fence, lease_id, state, phase
```

`host_identity` is the registered physical pool identity. The tuple of request
key, command ID and cluster attempt must match. An accepted-but-not-yet-granted
request has `phase=queued`, a durable `host_run_id`, and null attempt/fence/lease
fields. It is not a physical grant. Cancellation with a null fence is permitted
only if the host still has no attempt in the same cancellation transaction.
A missing lookup result contains
`found=false` and the matching envelope; it does not authorize a new submission.
A proven capacity rejection contains `accepted=false` and
`non_acceptance_proven=true` plus the matching envelope, with no external handle.

Terminal responses need separate `tree_exited=true` and
`resources_released=true`. Success additionally needs `artifact_committed=true`.
Other evidence such as compute completion and log completion stays separate.
The host's existing atomic submission, StateStore, Coordinator, leases and
ProcessSupervisor remain authoritative. This patch adds `controller_fences` and
`cluster_requests` in that existing local store. A thread-local guard holds no
long-lived lock; `claim_submission` and `request_cancel` recheck the current
controller epoch inside their existing writer transaction. Cancellation also
rechecks the host attempt fence there. A higher epoch arriving during graph
preparation therefore prevents stale final admission.

The cluster request intent is durable before delegation to `PoolService.launch`.
A duplicate cluster key only reads its record. A crash between that intent and
host admission stays unknown rather than replaying a possibly accepted launch.
Only an explicit pre-admission queue rejection with no durable run can be
recorded as `non_acceptance_proven`. Receipt counts have host-side retention
limits. Lookup never starts a job or creates a cluster request record.

The same host transport now exposes `execution.invocation.v1` with
`plan.submit`, `plan.details`, and `plan.cancel`. Bodies use the shared strict
`PlanSubmitControl`/`PlanLookupControl` models. `PoolService.plan_cancel`
authorizes through plan details before invoking the existing coordinator.
Lifecycle plan RPCs return compact counts/status/result location within the
64 KiB lane; direct plan details remain available for the application facade.
Pool transport EOF has code `response_unavailable`; socket timeouts remain
distinct exceptions so submit adapters can report uncertainty without parsing
localized messages.

## Administrative CLI

`python -m operon.cluster --config cluster-client.json` supports `migrate`,
`submit --plan plan.json --request-id KEY`, `status RUN`, `lookup KEY`,
`cancel RUN`, and `events --after CURSOR --limit N`. Configuration is strict:

```json
{"format":"operon.cluster-client","schema_version":1,"principal":"alice","dsn_environment":"OPERON_CLUSTER_DSN","schema_name":"public"}
```

The DSN is read from the named environment variable and never printed. This is
a trusted service-account administrative client, not a public principal
impersonation endpoint. It returns machine-readable JSON and uses the same
repository transactions. Administrative commands do not automatically start a
scheduler. `python -m operon.cluster --config controller.json serve` explicitly
owns one `ClusterController`, its dedicated leadership connection, bounded DB
and remote I/O workers, node observations, signal handling and shutdown cleanup.
No scientific jobs are cancelled by controller shutdown; uncertain in-flight
receipts remain durable and reconcile after takeover. Migrations are explicit,
not performed as a side effect of `serve`.

The strict `operon.cluster.daemon.ControllerSettings` model uses format
`operon.cluster-controller`, schema version 1, `principal`, `cluster_id`,
`controller_id`, `dsn_environment`, `schema_name`, `nodes`, and `prepared`.
The same controller configuration also supports administrative commands.
Each node declares a unique `node_id`/physical `capacity_domain`, executor
`ssh` or `slurm`, a `TargetSpec`, and operator-verified environments/storage/
devices. SSH nodes additionally require the expected host `host_identity`.
Node `ssh` settings require `host`, `username`, pinned `host_key` (`type`,
`base64`), `app_dir` and `workspace`; optional `port`, `python`, `key_path`, and
`auth` (`agent`, `key`, `password`) reuse existing SSH support. Password and
passphrase providers are named environment variables, never inline secrets.
No password, DSN or raw driver exception is printed.

Each preparation names exactly one source `plan_id` (pre-admission template) or
an already-admitted `run_id` (explicit compatibility), plus `unit_id`, `node_id`, `spec_digest` (the shared
`sha256_hex` of the immutable UnitSpec), `payload_file`, raw-file
`payload_sha256`, and optional committed `binding_id`. Relative files resolve
against the configuration directory. Startup hashes the payload and compares
the unit specification through an authorized PostgreSQL read before scheduling;
files are then held as immutable control data. A unit with an environment
requirement needs a committed binding ID. Preparation changes require an
explicit controller restart. Missing preparations remain ineligible.

SSH files now use the strict `InvocationTemplate`: configured `workspace`, full
immutable `source_plan`, `source_unit_id`, and the existing node-relative
`PlanExecutionBinding`. The controller derives a deterministic single-unit
RunPlan, preserving code, parameters, resource/output contracts and source IDs,
changing only local placement and recording the original plan/unit digest and
placement in `execution_policy.cluster_projection`. The projected identity is
recomputed. Already-declared external input bindings retain their paths/hashes;
the host validates their actual bytes before admission. Plan-keyed templates
need no admitted run at controller startup; the immutable `plan_id` in the ready
row selects them later. Run-keyed templates additionally check the stored source
plan identity. No new placement path sends a legacy graph.

The fenced `cluster.plan.submit/lookup/status/cancel` namespace requires both
`cluster.controller_fence.v1` and `cluster.invocation.v1`. The submit payload
contains strict `RunPlan` and `PlanExecutionBinding` records plus source lineage.
The host uses `PoolService.submit_plan` with the durable cluster claim's explicit
host run ID; that internal hook checks ownership/request/binding collisions.
The request envelope is tagged `submission_kind=plan`, preventing lookup or
cancellation through the legacy graph namespace. Plan status/cancellation use
the existing plan service. Terminal receipts require supervisor tree-exit proof,
released host resources, and an owned committed artifact for success. Lost
responses reconcile the original request on the same host without submitting
again. Older graph placements retain lookup/cancel support, but the SSH adapter
refuses new graph launches and never falls back when the invocation capability
is unavailable.

Same-host dependent units retain their full frozen source plan in a
`ConsumerTemplate` until the producer succeeds. After bounded placement ranking,
`ClusterRepository.producer_receipts` reads at most 128 committed identities for
the same principal/run. The scheduler persists a `ConsumerIntent` containing
producer command/request/attempt/fence/artifact identities before dispatch.
It requires the selected node and physical host to match every producer. No
controller-supplied output path is accepted as an artifact binding.

The existing `cluster.plan.submit` operation accepts this intent under
`preparation` and requires `cluster.same_host_artifacts.v1` in addition to the
invocation/fence capabilities. The host calls `SharedConsumerPreparer`, which
checks frozen source identities and named ports, proves the owned producer tree
stopped and resource lease released, verifies committed files and references,
then retains them and builds the local single-unit projection. Raw incoming
audited projections cannot bypass that host operation. Only the resulting
host-owned binding reaches `PoolService.submit_plan`. Status/cancel retain the
same durable cluster key and host run ID. Successful host receipts expose
`host_unit_id` and `{artifact_id,digest}` for the next consumer's verification.

Cross-host transfer remains explicitly unsupported. This slice supports direct
command/Python/R port bindings; control-only edges and native boundary aliases
without a direct frozen port mapping are rejected. Configure one eligible node
for a dependent chain: this patch does not add automatic data-locality placement
or move producers between nodes. A claimed preparation interrupted before host
admission stays recovery-required and retains its pins; it is never silently
rebuilt or resubmitted. Preparation-reference release/retention is still an
explicit lifecycle integration boundary. New focused tests use real local
journals/files with synthetic containment evidence; actual process and remote
multi-unit acceptance remains separate and was not run by this delegated task.
Unsupported preparation leaves the unit unclaimed and records a bounded entry
in `ClusterController.preparation_errors`; unrelated pending dispatches continue.

Projected invocations also require `maximum_attempts=1` until explicit remote
retry lineage is supported. Larger values are rejected without rewriting the
frozen policy. Existing admitted retrying runs remain observable: a terminal
attempt cannot make the cluster receipt terminal while its run/unit is active.

Invocation receipts snapshot run/unit/latest-attempt/lease metadata, read bounded
supervisor launch and tree-exit records outside the state lock, then recheck the
snapshot before reporting. Changed attempt selection/revisions produce an
uncertain receipt. `stopped_attempt_proof(invocation_root, attempt)` is the
read-only callback also available to artifact-binding validation. The proof must
match attempt/fence and durable launch process identity; an existing
`attempt.process` must match too. `never-spawned` can prove only failed/cancelled
attempts with an owned failed/no-PID launch record, never success. Success also
requires zero exit code, released resources and a committed receipt matching
this run/unit/attempt/fence/location/digest. Log completion is not reported before
the matching containment proof. Focused receipt tests use synthetic process
evidence and do not replace actual supervisor/two-host acceptance.

Startup and periodic lookup-only
probes check capability, configured controller authorization, host identity,
physical capacity identity, target and pool epoch. Host receipts now include
`host_pool_epoch`, `capacity_domain` and `target` for this purpose. A failed probe
marks the node offline; elapsed heartbeat is never used as process-death proof.
Only the configured service-account principal's ready units are dispatched.

Slurm payloads contain resources, immutable `script_path`, `stdout_path`,
`stderr_path`, `python`, `invocation_path`, `script_sha256` and
`invocation_sha256`, plus optional `slurm_cluster`. Startup checks the staged
script/invocation using remote checksums, verifies the script exactly equals
`allocation_script(...)`, and runs the actual Slurm capability/accounting probes.
The script invokes the existing allocation worker directly, without a host
pool. Compute inventory is explicitly site-provisioned, not inferred from the
gateway host. Periodic observations share the reserved bounded poll worker;
they never occupy the cancellation worker. Successfully submitting/observing a
Slurm job still does not satisfy artifact collection or target acceptance gates.

`tests/test_cluster_daemon.py` contains configuration and lifecycle fixtures,
not live controller deployment evidence. This connects the explicit controller
process lifecycle; it does not claim complete K11 application/API integration.

## Slurm hook and limitations

`SSHCommandTransport(lease)` leases the existing authenticated Paramiko client,
quotes literal argv for the SSH exec boundary, bounds stdout/stderr to 1 MiB,
and closes timed-out channels. It also stages immutable scripts through SFTP.
It introduces no new SSH library and no ProxyCommand.

`SlurmExecutor.probe(node_id)` requires `sbatch`, `squeue`, `sacct`, `scancel`,
and `scontrol`, successful accounting reads, persisted job comments, and an
inspectable site policy that does not force requeue. The stable token is saved
in PostgreSQL before `sbatch --parsable --no-requeue`; it is sent in both job
name and comment. Returned IDs are persisted by the controller's observation
transaction. Lost response, malformed receipt, missing accounting, or multiple
matching jobs remains `recovery_required`, with no automatic resubmit.

Prepared Slurm payload:

```text
resources: {account, partition, cpu_threads, memory_bytes, wall_seconds}
script_path, stdout_path, stderr_path: absolute reachable storage paths
accounting_start: persisted scheduler-local ISO timestamp before submission
slurm_cluster: optional expected cluster name from sbatch's parsable receipt
```

`allocation_script` invokes the existing invocation worker through
`operon.cluster.executors.allocation_worker`. The allocation worker requires
`SLURM_JOB_ID`, clamps configured budgets to Slurm values, CPU affinity and
available cgroup v2 ancestor limits, and never starts a host-wide pool or
installs packages. Site-specific GPU resource mapping is explicitly unsupported
until verified. This checkpoint uses the native invocation worker; all other
language/package paths need their shared kernel integration before claiming
coverage. Actual hard containment remains the site's Slurm/cgroup policy.

Queue pending is not timeout. Known active jobs use `squeue`; completed/unknown
jobs reconcile via `sacct`. Polls are spaced at least 10 seconds per observed
attempt. Cancellation sends `scancel` only after current token ownership matches
the saved job ID, then waits for terminal evidence. Scheduler COMPLETED means
compute stopped; it remains `committing` until the artifact collector verifies
and commits outputs.

Slurm's docs confirm the command behavior and the site-policy caveat:
[sbatch](https://slurm.schedmd.com/sbatch.html),
[squeue](https://slurm.schedmd.com/squeue.html), and
[sacct](https://slurm.schedmd.com/sacct.html). In particular, stored comments
depend on `AccountingStoreFlags=job_comment`, and `ForceRequeueOnFail` can
override `--no-requeue`.

## Coordinated test handoff

No test has been run by this delegated task. Root should run the consolidated
batch after integration and preserve logs under the project diagnostics area.

```text
python -m pytest tests/test_cluster_placement.py tests/test_cluster_recovery.py tests/test_cluster_host.py tests/test_cluster_cli.py tests/test_slurm_executor.py
OPERON_TEST_POSTGRES_DSN=<disposable PostgreSQL 17 service DSN>
python -m pytest tests/test_cluster_repository.py
```

`scripts/cluster_acceptance.py` is the grouped K12 evidence harness. Its
`--plan-only` mode writes `not_run` evidence without invoking pytest. Normal
execution separates module/mock fixtures, real local host/worker integration,
and the opt-in real PostgreSQL group, with commands, JUnit counts, bounded
runtime, platform/interpreter/dependency versions and source hashes before and
after. Existing evidence files are never overwritten. Two-host SSH and actual
Slurm remain explicit `not_run` entries; this harness cannot certify them from
local or mocked results. Gate statuses remain `not_accepted` for manual review.

The SQL migration resource is included by the `operon.cluster` package-data
entry in `pyproject.toml`. No wheel build or installed-wheel inspection has yet
been run; runtime extras still need maintainer-selected, qualified pins.

## Terminal recovery and explicit resume boundary

`Coordinator.recover` now accepts executor terminal evidence only when an owned
process identity is supplied and the tree is confirmed stopped (success also
requires exit code zero). It routes that evidence through the existing
`_finalize` path, including artifact publication and lease release. A terminal
label without proof is quarantined. Recovered success uses the already allowed
`recovery_required -> succeeded` transition; it does not invent an invalid
`recovery_required -> committing` transition. Publication receipts are retained.
`tests/test_cluster_terminal_recovery.py` is a proof-routing fixture, not real
process-death or crash acceptance.

Explicit standalone failed/cancelled-run resume is implemented in
`operon.export.resume.attach_verified_resume(store, *, root, parent_run_id,
run_id, run_identity, request_id, principal, environment_store)`. The kernel
calls it under its existing exclusive controller FileLock, after submitting a
fresh child and before the scheduler runs. Exact `runs.plan_key` identity binds
plan, inputs and environments; graph/parameters/unit definitions are compared
again. The parent remains terminal. Successful units are reused only as an
ancestor-closed subset after full artifact and file-reference verification.
Active/uncertain attempts, unreleased resource/environment leases, absent or
inconsistent supervisor tree proofs, and changed artifact receipts fail closed.

`StateStore.attach_resume` rechecks revisions, ownership, exact identities and
immutable artifact records in one transaction. It records `unit_reuses`, pins
source artifacts for the child, emits `unit_reused`/`run_resume_attached`, and
stores `execution.resume_parent_run_id`. Reused units have zero new attempts;
the implementation does not fabricate executed history. Durable published
descriptors are rematerialized on same-request replay after interruption.
Repeated failed resumes can inherit prior attachments, always re-verifying
their bytes. This is explicit lineage reuse, not a cross-run cache.

`commit_existing` now separates content digest from attempt/fence publication
identity. Equal content from distinct attempts cannot overwrite ownership or
payload location. Retention excludes attempt scratch containing referenced
artifacts, including resume attachments. `tests/test_export_resume.py` covers
state/file behavior using synthetic process evidence; it is not a real process
containment acceptance gate and has not been executed yet.

The DB suite creates/drops only a UUID-named schema it owns. It tests concurrent
same-key submission, replay before quota, conflicts, real rollback, actual
commit followed by an injected lost-reply exception, migration checksum guards,
exclusive leadership/epoch, pinned recovery, cancellation and reserved lanes.
The lost-reply injection is a fault fixture over a real commit, not proof of a
real network partition. The SSH and Slurm transport fixtures are adapter tests,
not K09/K10 end-to-end evidence.

Unfinished integration remains explicit: authenticated public cluster endpoints;
real controller deployment qualification; automatic environment/storage staging and immutable
binding publication; artifact collector; complete retry policy; bounded event
retention with replay-window tombstones; disk/WAL admission watermarks; qualified
psycopg extras and installed-wheel resource verification; and performance comparison against
the recorded K00 baseline. None of these is asserted complete here.
