# Backend implementation contract

Status: **normative design for the next implementation, not an implementation or
acceptance report**. Date: 2026-11-14. Contract revision: 1.

This fixes the engineering choices in
[the execution/cluster roadmap](execution_portability_cluster_roadmap.md).
Where that roadmap offers choices or sketches, this contract takes precedence.
The coding implementer may choose private helper names and algorithms with the
same observable behavior. Changing service ownership, dependencies, persistence,
protocols, export semantics or acceptance gates requires a recorded design
revision, not a silent implementation shortcut.

## 1. Baseline, integration and scope

- Application baseline: upstream 5.1.9 at
  `600eed6f53b6db01f7391f408ade1e950d8679b3`.
- Existing working tree: `fix/3.0.1-installation`, HEAD `0f2c87cd`, with local
  Setup/maintenance, admission-control and native standalone changes.
- Implement in a new application worktree/branch derived from the pinned
  baseline. Preserve the existing dirty checkout. Record the carried patches
  and their regression tests before changing their implementations.
- Do not move active development back to a combined application/library main.
  Consume the latest independent library contract; coordinate library-builder
  metadata changes without rewriting scientific operators or changing their
  defaults. Keep library resources and code identities intact.
- No application version bump, release or infrastructure start is implicit in
  an implementation checkpoint. Publish only the exact accepted build.

The delivery units are K00-K12 below. Complete and verify them incrementally.
Do not implement Tauri, distributed HA or arbitrary Nextflow parsing as part of
the backend foundation. Their boundaries are fixed here so later work does not
require another engine.

## 2. Fixed technology choices

| Concern | Required choice | Explicit exclusions |
| --- | --- | --- |
| Application/management Python | CPython 3.11, using the existing validated runtime recipe; source compatibility tests on 3.11 and 3.12 | No incidental runtime upgrade; scientific environments may select other versions |
| External request validation | Existing Pydantic 2, strict models with `extra='forbid'`; exported JSON Schema | No permissive dictionary parsing in new public endpoints |
| Engine values | Existing frozen dataclasses plus immutable tuples/records at domain boundaries | Do not replace engine contracts wholesale with ORM objects; a frozen dict-containing object is not deeply immutable |
| YAML | Existing custom PyYAML SafeLoader, duplicate-key/alias safeguards, explicit versioned schema | No expression evaluation, arbitrary tags, or Groovy evaluation during import |
| HTTP/control API | Existing FastAPI + Uvicorn, one service worker; async I/O endpoints with bounded offload for synchronous operations | No Flask/Django rewrite; no multi-Uvicorn-worker embedded schedulers |
| Host pool transport | Existing framed protocol and bounded `ControlLoop`, incorporating local admission/rejection fixes | No unbounded thread-per-connection; no simultaneous incompatible socket rewrite |
| Host state | `sqlite3`, existing StateStore/Coordinator/outbox on a local filesystem | No SQLite on shared/network storage |
| Cluster state | PostgreSQL 17, psycopg 3 with `psycopg_pool`; explicit SQL repository and numbered SQL migrations | No Redis queue, Celery, SQLAlchemy or Alembic in this phase |
| Scientific processes | Existing ProcessSupervisor/Executor ownership model; argument-vector subprocess launch | No bare launch outside the supervisor; no unbounded `capture_output` for job logs |
| SSH/storage | Existing Paramiko 3.5-compatible API, authenticated tunnels and SFTP | No second SSH library; no arbitrary user-provided ProxyCommand shell execution |
| Python build locks | Existing pip builder extended with hash-pinned wheelhouse; pip-tools as a build-only resolver | No package resolution/installation during an offline exported run |
| R packages | renv lock at build time, materialized package directories and explicit R runtime | An `renv.lock` file alone is not a runnable environment |
| Binary/Conda environments | Target-native build, explicit package lock and conda-pack relocation adapter when the source is Conda | Never raw-copy a Conda/venv directory and declare it portable |
| Native compilation | CMake + Ninja for new C/C++ fixtures/adapters; preserve an existing declared tool build recipe | No compiler requirement on the package recipient |
| HPC | Slurm CLI adapter through the existing remote transport | No parallel Operon host-global allocator inside a Slurm allocation |
| UI | Existing React/TypeScript/React Flow | Backend work does not require a frontend rewrite |
| Future desktop | Tauri 2/Rust host + management sidecar, same HTTP/service contract | Do not rewrite scientific Python/R in Rust |

Pydantic, FastAPI, Uvicorn, Paramiko and other existing dependencies retain the
versions in the inspected build until compatibility checks justify a change.
K00 records exact versions and source hashes in target-specific lock manifests.
New psycopg/pip-tools/renv/conda-pack versions are selected once by the build
maintainer, tested and pinned there. A design document cannot certify an untested
patch release. Release builds must fail on a missing lock; they cannot resolve
`latest` or an open-ended `>=` requirement on the release path.

PostgreSQL and psycopg are **cluster-service extras**, not desktop or standalone
requirements. pip-tools, compilers and package resolvers are build tools, not
background startup services. The existing management runtime includes some
Form/NumPy infrastructure; do not describe it as containing no Python or NumPy.

## 3. Processes, authority and concurrency

### 3.1 Process roles

| Role | Owns | Cannot own |
| --- | --- | --- |
| Desktop/CLI/MCP adapter | User request, revision check, presentation, event subscription | Scientific job lifetime or resource grants |
| Application service | Workflow CRUD, validation, preparation, export requests, task facade | A second allocator next to a host pool |
| Cluster controller | Durable placement, dependencies between remote units, transfer prerequisites, cluster receipts | Host physical RAM/CPU leases or a Slurm resource allocation |
| Host pool | One capacity domain, admission ledger, resource leases and local attempt lifecycle | Another host's physical capacity |
| Allocation runner | One Slurm allocation's internal tasks and sub-budgets | Resources beyond the allocation/cgroup or a host-global pool claim |
| Supervisor | Owned process tree, launch receipt, poll/cancel/adoption | Scientific task state inferred solely from PID existence |
| Worker | Scientific operator execution and managed allocations inside its grant | Enlarging its grant or installing dependencies |
| Standalone controller | One exported run and its local executor/state | Desktop profile, global registry or persistent host-pool service |

The application service may be embedded in the current desktop backend. The
cluster controller is a persistent server process. A standalone package creates
an isolated local capacity domain and does not connect to the user's installed
Operon daemon. Running several standalone packages is not claimed to share one
global allocator; each accepts an explicit budget and reports that boundary.

For unmanaged SSH clusters, provision one registered service account/pool per
physical capacity domain and map clients' scheduling principals onto it. Two SSH
aliases or OS accounts on the same unpartitioned machine are not two capacity
nodes. Inventory rejects overlapping registrations unless an administrator has
defined independently enforced cgroup/VM allocations. Existing per-account
local pools do not coordinate all unrelated OS users; Slurm/site resource
management is the supported boundary for that multi-user requirement. External
unmanaged workloads remain a pressure/containment concern, not capacity the
controller can guarantee away.

### 3.2 Fixed concurrency model

Keep existing synchronous scientific orchestration behind short service methods.
For the new cluster controller use one async HTTP event loop, one scheduler
thread, a bounded database executor (8 threads/connections), and a bounded SSH
I/O executor (8 threads). There is at most one outstanding scheduling pass; long
RPCs are executor work, never part of a scheduling transaction. Executors have
explicit admission semaphores; `ThreadPoolExecutor`'s internal queue is not a
backpressure mechanism.

Host `ControlLoop` keeps its 32-handler default. Carry the bounded rejection
lane and principal limiter. Cancellation/status have a reserved service lane so
bulk submission or browsing cannot occupy every dispatch slot. Slot limits are
configuration, not scientific data-size restrictions. Do not increase handler
counts to hide a database bottleneck.

Implement that reserved capacity as an optional dedicated lifecycle listener
with 4 handlers using the same framing/authentication and shared service state.
Advertise its endpoint through pool discovery/handshake capability
`control.lifecycle_lane.v1`. It permits only bounded status, cancellation and
session-detach requests, with a 64 KiB frame ceiling; it cannot submit jobs,
install dependencies, browse, or retrieve full logs. Principal lifecycle quotas
still apply. Legacy clients keep their existing endpoint, but do not receive a
false guarantee of the new reserved lane. New clients use it when negotiated.
This is an additive endpoint, not a replacement wire protocol or allocator.

SSH connections/channels and database connections are leased, not shared
concurrently without ownership. A long SFTP listing does not hold a channel
needed for cancellation. Use separate bounded transfer/browse/control lanes.
Closing a UI session cancels its browse work, not its accepted scientific jobs.

The GIL is not solved by `async`. JSON decoding, graph compilation, hashing and
compression remain bounded/offloaded work. First cap requests and profile;
introducing a Rust decoder or process pool requires measured evidence, not an
assumption about Python speed.

## 4. Module layout and dependency rules

New modules are small domains around existing entry points:

```text
operon/
  contracts/                 # wire models and generated schemas
    workflow.py run_plan.py invocation.py environment.py storage.py errors.py
  planning/
    compiler.py resolver.py identity.py validation.py
  execution/
    runner.py invocation.py context_bridge.py worker_main.py
    adapters/python_sdk.py python_script.py r_script.py command.py
  environment_store/
    service.py generations.py locks.py verification.py builders.py
  export/
    service.py planner.py collector.py builder.py verify.py launchers.py
  storage/
    service.py references.py mounts.py browsing.py
  cluster/
    service.py scheduler.py placement.py receipts.py repository.py
    postgres.py migrations/ executors/ssh_pool.py executors/slurm.py
  engine/                    # existing host engine; extend, do not duplicate
  remote/                    # existing SSH/provision/handshake/transfers
```

This is a destination layout, not permission to move every file in one commit.
Existing `application.py`, `workflow_spec.py`, `environments.py`, `portable.py`
and `src/web/execution*.py` initially delegate to the new modules. Their API
compatibility tests must pass before removing old private implementations.

Allowed imports point inward:

```text
CLI / HTTP / MCP / UI adapters -> application services
application -> planning / export / storage / environment / cluster
planning -> contracts + catalog interfaces (metadata only)
execution -> contracts + SDK + existing memory / artifact / supervisor code
engine -> contracts and execution interfaces (no web import)
cluster -> contracts + repositories + executor clients
```

Pure plan/contract modules must not import `src.web`, scientific operators,
Matplotlib, Torch, Paramiko or FastAPI. Catalog lookup is injected. The portable
execution kernel must not import a web service to obtain Context or load Form.
If this dependency exists today, extract the specific runtime dependency first,
preserving its behavior and tests.

## 5. Wire contracts and identities

Use discriminator fields `format` and integer `schema_version`. Public JSON
models reject unknown required behavior, invalid enums, NaN/Infinity, duplicate
keys and booleans supplied as integer resource quantities. Numeric resource
values are integer bytes/threads/seconds after parsing at the UI/YAML boundary.
Event cursors and database sequences are decimal strings on the wire, avoiding
JavaScript integer precision loss. Binary scientific data never goes in JSON.

| Record | Required fields |
| --- | --- |
| RunPlan v1 | `plan_id`, `workflow_revision`, `units`, `edges`, `parameters_digest`, `implementations`, `environment_requirements`, `storage_bindings`, `execution_policy`, `compiler_version` |
| UnitSpec | `unit_id`, `node_ids`, `invocation`, `input_bindings`, `output_contracts`, `resource_request`, `placement`, `retry_policy`, `cache_contract` |
| InvocationSpec v1 | `kind`, `entrypoint` or `argv`, `code_ref`, `parameters_ref`, `environment_ref`, `cwd_policy`, `event_protocol`, `output_manifest` |
| ArtifactRef v1 | `artifact_id`, `representation`, `locations`, `logical_metadata`, `size_bytes`, `digest`, `verification`, `owner`, `lifetime` |
| StorageRef v1 | `storage_id`, `relative_path`, `version`, `digest` when known; location credentials are not part of the record |
| EnvironmentRequirement v1 | `target`, `runtime`, `dependency_lock`, `resources_manifest`, `required_capabilities`, `recipe_digest` |
| EnvironmentBinding v1 | requirement digest, node/target, immutable generation ID, content digest and verification receipt |
| AttemptReceipt v1 | run/unit/attempt ID, command ID, executor kind, external handle, host/pool identity, fence and evidence revision |

**Plan versus binding:** a workflow plan has environment requirements and stable
storage references. Scheduling produces an append-only binding record for the
chosen node, environment generation and input snapshot. Do not mutate the plan
to insert a machine-local path. Execution identity hashes the resolved plan and
the binding's content identities; presentation/location changes are separate.

Use the existing canonical JSON encoder, now explicitly named
`operon-canonical-json-v1`, for hashing. Freeze test vectors for strings,
non-ASCII text, integers, floats, nulls and ordering. Foreign-language adapters
consume the canonical bytes and digest instead of inventing their own float
serialization. Domain-separate hashes (`operon:run-plan:v1`,
`operon:environment:v1`, etc.). Never hash timestamps, UI coordinates,
absolute installation roots or a mutable default value into code identity.

Implementation identity includes package/version, code digest, resource digest
and ABI-relevant SDK behavior. Declaration/document hashes remain audit fields.
Run/cache identity additionally includes frozen parameters, input content,
explicit conversions, environment contents, target ABI, numerical execution
policy and bound randomness. An unspecified seed or side effect disables cache
reuse unless the existing explicit cache contract permits it.

### 5.1 Python interfaces (normative shape)

The following names describe required interfaces; record classes live in the
modules above. These are contracts, not runnable snippets.

```python
class WorkflowCompiler(Protocol):
    def compile(self, spec: WorkflowSpec, values: FrozenParameters,
                catalog: CatalogSnapshot) -> RunPlan: ...

class EnvironmentStore(Protocol):
    def inspect(self, requirement: EnvironmentRequirement,
                target: Target) -> EnvironmentReadiness: ...
    def prepare(self, requirement: EnvironmentRequirement,
                target: Target, request_id: str) -> PreparationReceipt: ...
    def acquire(self, generation_id: str, attempt_id: str) -> GenerationLease: ...
    def release(self, lease: GenerationLease, proof: AttemptStopProof) -> None: ...

class InvocationAdapter(Protocol):
    def prepare(self, invocation: InvocationSpec,
                context: InvocationContext) -> PreparedInvocation: ...
    def collect(self, prepared: PreparedInvocation,
                exit_receipt: ExitReceipt) -> OutputManifest: ...

class StorageService(Protocol):
    def stat(self, ref: StorageRef) -> StorageEntry: ...
    def list(self, request: BrowseRequest) -> BrowsePage: ...
    def materialize(self, ref: ArtifactRef, target: StorageBinding,
                    request_id: str) -> TransferReceipt: ...

class ExportService(Protocol):
    def plan(self, run_plan: RunPlan, request: ExportRequest) -> ExportPlan: ...
    def build(self, plan_id: str, request_id: str) -> BuildReceipt: ...
    def verify(self, build_id: str, target: Target) -> VerificationReceipt: ...
```

Keep the existing `Executor.launch/poll/cancel/reconcile` interface and
`ExecutionContext`/`ExecutionResult` boundary. New SSH/Slurm adapters implement
it or have one explicit mapping layer; do not create incompatible copies with
different terminal-state definitions. Invocation adapters prepare the command;
only Executor/Supervisor launches it.

`AttemptStopProof` is either verified process-tree exit or a durable no-launch
receipt proving that spawn never occurred. A failed preparation can release its
lease with the latter; a lost spawn response cannot. An exception alone is not
proof that a process was never created.

## 6. Compilation, units and data handoff

The compiler performs these passes, in order:

1. Static parse/schema validation; no operator import or dependency install.
2. Resolve saved values and catalog snapshot; detect missing node IDs/ports.
3. Expand pinned route operators with deterministic namespaced IDs and exact
   outer/inner parameter mappings.
4. Validate DAG and format contracts; insert only explicitly registered,
   representation-preserving converters. Ambiguous semantic conversions fail.
5. Derive environment requirements and placement constraints.
6. Form execution units; derive resources, transport and scratch requirements.
7. Canonicalize, persist the plan and report per-node blockers/warnings.

One node is the initial execution unit. A maximal same-environment chain may
remain in one existing native worker when the legacy execution path requires
in-process Form lifetime. **Do not split it until every outgoing boundary has a
valid materialization codec.** Record the nodes in UnitSpec. Later fusion is
allowed only with identical observable parameter/cache/artifact semantics.

Version 1 boundary codecs:

- file/reference: owned file or directory manifest;
- NumPy array: `.npy` plus shape/dtype/axis metadata, mapped when possible;
- table: explicit CSV/TSV plus schema for baseline interchange;
- scalar/list/metadata: typed JSON with bounded size;
- existing disk Form codec: adapter preserving `info` and `axis_info`.

Arrow/Parquet may be used by an existing declared converter, but are not a new
mandatory management dependency. Sparse matrices remain sparse unless an explicit
budgeted converter requests dense data. Object-dtype arrays and arbitrary Python
objects have no automatic cross-language codec; use a declared adapter or return
`unsupported_boundary`. No pickle-based universal transport.

The compiler may materialize at a language/environment boundary. It must not
claim streaming when either endpoint only supports full data. Existing supported
streaming paths preserve bounded owned blocks and ACK/backpressure behavior;
production Reader streaming is not inferred from a test adapter.

## 7. Invocation and worker ABI

The prepared attempt directory contains immutable `invocation.json`,
`parameters.json`, `inputs.json`, generation binding and a writable `outputs/`,
`scratch/`, `logs/`. Paths passed to workers are resolved from the attempt root,
not the process-wide current directory. Never call global `os.chdir`.

`argv` is a list of literal arguments and typed substitutions (`input`,
`output`, `parameter`, `resource`). Resolve substitutions without shell parsing.
The shell adapter writes an explicit script file and invokes its declared shell;
it does not interpolate arbitrary JSON values into shell source.

Worker entry points:

- Native SDK: `python -m operon.execution.worker_main --invocation PATH`.
- Python script: a generated shim receives input/parameter/output files and
  invokes the stored script using its declared interface.
- R: `Rscript --vanilla adapter.R --invocation PATH`; a locked JSON reader and
  boundary helper are part of that environment, not fetched at runtime.
- Shell/native binary: exact executable and argument vector; outputs are checked
  against the declared manifest after exit.

All adapters get the same normalized resource grant and attempt identifiers.
The native Context bridge must preserve step parameters, info/axis metadata,
logger, memory manager, spill, artifact registration and cancellation. Do not
implement it with `memory=None` and no-op events.

stdout/stderr are bounded append-only logs, not the event protocol. Structured
events are written to a separate per-attempt JSONL channel/file with sequence,
attempt ID and size limits; external tools may provide only logs and final
outputs. Readers tolerate a partial last line after a crash. Do not parse
arbitrary console text as a success receipt.

R adapters set an explicit isolated package search path and initialize their
locked helper before running user code; `--vanilla` alone does not choose the
correct package library. Every language adapter records resolved executable,
environment generation and effective limits in its attempt receipt.

Output manifest publication is atomic after validation. A zero process exit code
with a missing/wrong output is a failed attempt. Conversely, a complete output
manifest does not prove child processes have exited. Supervisor evidence and
artifact validation are independent requirements.

Cancellation goes through the existing owned process tree. Preserve Windows
process ownership and Linux process-group/cgroup supervision; port existing
recovery tests. A timeout never authorizes killing unrelated Python processes.
If ownership/termination cannot be established, keep `recovery_required` and its
resource/environment references.

## 8. Immutable environment store

### 8.1 Layout and preparation

```text
environment-store/
  blobs/sha256/<digest>                 # immutable runtime/wheel/resource blobs
  staging/<preparation-id>/
  generations/<generation-id>/
    manifest.json
    runtime/
    packages/
    resources/
    verification.json
  references/                          # current aliases are pointers, not data
```

State is `requested -> resolving -> building -> verifying -> ready`, or
`failed/cancelled`. A `ready` generation is immutable. Acquisition references
its identity, not a mutable alias such as `default` or `protein-env`.

Prepare under a per-requirement/target lock. Download/build/verify outside engine
transactions; commit a completed generation using same-filesystem atomic publish.
The filesystem publish and DB registration are not one transaction: a durable
preparation journal reconciles either crash order. A marker without a completed
verification manifest is never ready.

Dependency checks reuse a ready receipt during the session for the same immutable
generation. Install/repair changes its generation, invalidating affected checks.
Imported external mutable environments retain existing EnvironmentGuard
exclusion and a content fingerprint; do not relabel them immutable. Copy/build a
managed generation before promising reproducible portable export.

A lease is acquired before spawning. Release requires confirmed tree exit or a
verified supervisor handoff. GC uses reference counts plus process evidence;
lease TTL alone cannot delete an environment underneath a live worker.

### 8.2 Resolution and packaging rules

1. Start with each invocation's complete declared requirement set.
2. Group requirements by target, language, runtime ABI and compatible native
   tool policy. Reuse identical resolved closures immediately.
3. Attempt compatible-group merges using the real resolver and deterministic
   ordering; cap merge attempts/time. On conflict or timeout keep groups
   separate. Minimize environment count heuristically, not exhaustively.
4. A single interpreter can service different private site-packages directories
   in separate processes when ABI-compatible. Never load conflicting extensions
   in one process or rename imports to simulate versions.
5. Record actual downloaded artifact hashes, wheel tags, package versions,
   external executable digests and declared resource files.
6. Verify imports/tool probes and a relocated execution on the target.

Python export uses the existing relocatable CPython runtime builder, exact wheel
locks and an offline wheelhouse. Prefer wheel artifacts; an sdist is built into a
wheel on an isolated target builder before distribution. Invocations use
interpreter-relative paths and disable user site-packages. No host PATH or
global `PYTHONPATH` fallback for required tools/modules.

R environments materialize a platform-matched R runtime and renv-locked packages
on the build target. Resolve renv cache links into package-owned files. Native
libraries and R startup configuration are part of verification. Conda-sourced
R/native environments use the conda-pack adapter; non-Conda R runtime archives
use their own verified relocation recipe.

Conda relocation may require prefix fixups. Preserve the immutable packed input
blob, extract/fix up into a destination-specific staging generation, verify and
publish it **before the first attempt**. This is offline local preparation, not
dependency downloading. Moving the package again creates a new binding from the
original packed blob; do not patch an active generation in place. Distinguish
archive-content identity from relocated deployment identity.

Linux-only tools remain Linux-only. Container delivery is an explicit optional
profile, not a silent fallback. Required externally licensed software or missing
model weights block `offline_complete`; runtime OS/GPU-driver prerequisites are
reported separately. Resource collection follows builder manifests, including
PDBFixer templates/XML, not just imported `.py` files.

## 9. Local state, transactions and lifecycle

Retain existing RunState and AttemptState names. Do not replace the stable task
API with a second state machine. Additional executor phases are detail fields.

```text
blocked -> ready -> admitted -> starting -> running -> committing -> succeeded
                  |              |           |            |
                  +--------------+-----------+------------+-> failed/cancelled
                                 +-------------------------> recovery_required
```

`recovery_required` may reconcile into a live state or a proven terminal state.
Terminal-to-active transitions are forbidden; retry creates a new attempt.
`compute_complete`, `artifact_committed`, `tree_exited`, `logs_complete` and
`resources_released` remain separate evidence fields. Artifact failure may leave
compute complete and resources released while the attempt itself fails.

Submission transaction order:

1. Resolve authentication to a configured principal.
2. Look up `(principal, request_id)` before quota checks; matching replay returns
   the original receipt, different content returns `idempotency_conflict`.
3. Check/reserve queue counts, plan bytes, unit counts and preparation capacity.
4. Atomically write request, run/unit records and outbox commands.
5. Commit, then perform process launch/network actions through outbox consumers.

SQLite commit failure with unknown outcome returns `submission_uncertain` and
requires lookup by the original key. It cannot fall back to a file-only launch.
Retain compatibility files only as mirrors/recovery evidence.

No network call, process start/wait, hashing of scientific data or environment
build occurs while a StateStore/JobService state lock or DB transaction is held.
Maintain a checked lock-order DAG. Do not justify an inversion with a short
critical section. Cancellation publishes intent, releases locks, stops owned
processes, then records evidence and releases resources.

## 10. Cluster persistence and remote submission

PostgreSQL stores cluster placement metadata, not the existing host SQLite
tables copied verbatim. Required tables:

| Table | Key and important constraints |
| --- | --- |
| `controller_owner` | singleton cluster ID, epoch, owner receipt; one controller holds a dedicated session advisory lock |
| `nodes` | stable node ID; capacity-domain ID, capabilities, observed pool epoch, last heartbeat, health |
| `storage_endpoints` | storage ID and non-secret topology/config revision |
| `node_mounts` | `(node_id, storage_id)` unique; validated root/path mapping |
| `requests` | `(principal, request_id)` unique; digest and stable result receipt |
| `runs` / `units` | immutable plan identity, revision and lifecycle state; stable unit key within run |
| `placements` | attempt ID, node/executor, command ID, executor handle, controller epoch and host receipt |
| `transfer_jobs` | artifact/target identity, durable transfer ID and checkpoint |
| `quota_usage` | principal and scope counters, locked when admitting new work |
| `events` / `outbox` | monotonic event cursor; unique command ID; delivery status and reconciliation evidence |
| `environment_bindings` | requirement/node/generation bindings referenced by attempts |

Use parameterized SQL through psycopg 3. Mutating transactions use row locks and
unique constraints; counters update in the same transaction as admissions.
Use `READ COMMITTED` with explicit locking/CAS by revision, not application
scan-then-insert. Retry serialization/deadlock errors only inside pure DB
transactions; do not replay an external submission in a transaction retry.

Reserve the bounded PostgreSQL capacity by lane: six connections for ordinary
requests, one for scheduler transactions and one for lifecycle/status requests.
The leadership advisory-lock connection is separate and never serves work.
Use finite connection/statement/lock timeouts, with timeout results exposed as
structured errors. No request may hold a connection during remote I/O.

Numbered migrations have checksums and an exclusive migration lock. Changes are
additive while older readers are supported. Back up and verify before an
incompatible migration. No automatic destructive downgrade on an older binary.

A dedicated advisory-lock connection guards controller leadership. Losing it
stops dispatch immediately; it does not imply worker death. Reconnection requires
reconciliation and a new epoch. One controller is supported in this phase;
active-active failover is explicitly outside acceptance.

### 10.1 Host submission and fences

Persist a dispatch command and stable idempotency key before sending to a host.
Host `submit` is atomic and returns its run/attempt/lease receipt. If the reply
is lost, query the same key on the same host; never schedule a replacement on a
different host merely because a network timeout elapsed.

Keep controller epoch and host-pool fence distinct. Hosts store the highest
accepted epoch for each authenticated controller identity and reject stale
control commands. Existing live attempts remain reconcilable after epoch change;
a new epoch is not permission to duplicate or kill them without ownership proof.
Two controllers cannot obtain extra physical capacity: host admission remains
the sole final grant authority.

Heartbeat default is 10 seconds, suspect threshold 30 seconds, offline threshold
90 seconds; these are configurable observations, not task-failure deadlines.
An offline node's attempts become uncertain/recovery-required and keep their
ownership evidence. Only verified stop/fencing or an explicit operator recovery
decision allows rescheduling potentially side-effecting work.

### 10.2 Slurm adapter

Require a capability probe for required Slurm commands and accounting access.
Build an attempt script in reachable storage, then call `sbatch --parsable` with
validated account/partition/resources and a stable Operon submission token in
job metadata. Persist the returned job ID immediately.

Observe `squeue` for active jobs and `sacct` for completed jobs; normalize
pending/running/completing/terminal states without treating queue delay as a
worker timeout. Accounting delay is unknown, not a failed job. Cancellation uses
the persisted owned job ID and waits for evidence of termination. Do not enable
uncontrolled automatic Slurm requeue in this phase.

`sbatch` is not an idempotent API. After lost response, reconcile the token
against active/accounting records. No matching record under uncertain or
unavailable accounting is still ambiguous; do not automatically resubmit. This
design prevents blind duplication but does not claim exactly-once external
side effects across every scheduler failure.

Slurm controls resource admission. Run the package worker directly within its
allocation, with memory/CPU/device limits clamped to the allocation. Do not start
the normal host-wide managed pool. Submission of a whole unchanged Nextflow
project is a separate external-workflow adapter and cannot recursively acquire
an incompatible host-global reservation for all its child jobs.

## 11. Placement and resource accounting

Algorithm is deterministic bounded greedy placement, not exhaustive search:

1. Fetch at most 256 ready units per pass; use principal fairness/age ordering.
2. Filter nodes by OS/ABI, required environment/tool capabilities, devices,
   storage reachability, route affinity, explicit user placement and health.
3. Rank remaining nodes by estimated finish time: queue wait + missing-artifact
   transfer time + expected compute time. Tie-break by fewer missing bytes,
   oldest eligible unit and stable node ID.
4. Try admission on up to 4 candidates per pass. A capacity rejection is not a
   scientific retry and does not consume a scientific attempt retry budget.
5. Refresh on events or a 1-second tick; bound a scheduling pass to 50 ms of
   planning CPU work, with RPC completion handled separately.

The constants are initial configurable control-plane defaults. Persist observed
runtime/transfer EWMAs with sample count and confidence. Unknown costs use
explicit conservative defaults and remain visible in the placement explanation.
Do not claim globally optimal placement or fabricate scientific run estimates.

Preserve host startup-frozen capacity and the existing fair policy. Never add
the managed-memory sub-budget to its containing process reservation twice:

```text
physical_charge = process_reservation + transport_reservation + shared_buffers
managed_budget <= process_reservation
sum(active physical_charge) + management_reserve <= startup_capacity_ceiling
```

Apply the same accounting to language-conversion overlap and block fan-out. A
shared block is charged once physically, retained until all consumers release
it, and never counted as free while an unconfirmed consumer may hold it.
Scratch reservation, device IDs and CPU grants are separate resources. CPU
thread environment variables are passed to BLAS/OpenMP where appropriate, but
do not claim they hard-limit every arbitrary external executable.

On Slurm use allocation/cgroup limits. On unmanaged hosts preserve emergency
spill/pressure containment; real OS hard limits require supported platform
mechanisms. Native arbitrary output cannot be assigned a hard filesystem quota
merely by a logical counter. Report soft reservation versus enforced quota.

An arbitrary R/C/C++ process cannot spill its private heap on an Operon command.
For such invocations reserve the declared full-process peak, stage data through
budgeted file boundaries and apply supported OS containment. Reject an infeasible
full-mode invocation or request a genuinely chunk-capable adapter. Emergency
spill applies to managed data, not every allocation in a foreign runtime.

Retries retain the existing declared retry policy. A data/schema/parameter error
is not automatically retried. Transient infrastructure errors may retry only
after predecessor attempt termination/publication state is reconciled.

## 12. Storage, browsing and transfer

Introduce stable storage IDs and mount maps, never host-specific absolute paths
as universal identities. Each attempt resolves its own binding. A storage root
is configured by an administrator/user; manifests use normalized relative paths
with traversal rejection. Resolve symlinks under the configured policy and
verify the resolved path remains in an allowed root. Preserve permitted existing
absolute-path imports through explicit migration/binding.

Browse service API shape:

```text
POST /api/v1/storage/browse
  {storage_id, relative_path, cursor?, page_size?, hidden?, order?}
  -> {entries, next_cursor, listing_revision, order, complete}
POST /api/v1/storage/stat
POST /api/v1/storage/preview
POST /api/v1/transfers
GET  /api/v1/transfers/{id}
POST /api/v1/transfers/{id}/cancel
```

First page uses bounded directory enumeration, returning promptly without full
sorting. Default page size 200, maximum 1000; preview defaults to 64 KiB/100 rows,
maximum 1 MiB. These are configurable UI/control safeguards, not file-upload size
limits. Size comes from metadata, not file contents.

A cursor is opaque and scoped to authenticated principal, storage, directory,
filters and listing revision. Keep a bounded enumeration handle with 30-second
idle expiry; expired/changed cursors return explicit restart guidance. Entry
order is `filesystem` until an optional complete local/server index is ready.
Global alphabetical order is offered only from that index, not falsely simulated
by sorting each page. Storage-only SFTP browsing has the same bounded contract.

Reuse existing resumable transfer checkpoints, chunk verification and leases.
Add storage-to-storage bindings; shared storage produces a visibility probe
instead of a copy. Direct server-to-server transfer needs an authorized transport
route. If unavailable, report the route restriction before using desktop relay;
do not silently download all data to the user's laptop.

Separate control metadata from file payloads. File transfer size is governed by
available/allocated storage and explicit user policy, not the JSON frame limit.
Data remain on the server when only the UI selection, logs or bounded preview
are requested. Never use browse search as an unrestricted recursive scan by
default.

## 13. Portable package construction

One shared compiler feeds local/remote/export execution. The portable controller
uses the same invocation adapters, supervisor, artifact validation and memory
accounting, with an in-process local coordinator and package-local state.
No application UI, HTTP server, MCP daemon, global profile or registry is needed.

Build phases: plan -> acquire source/resources -> prepare target environments ->
assemble -> structural verification -> relocation/probe verification -> optional
scientific acceptance. Every phase has progress, cancellation and a durable
build receipt. A partial directory cannot be presented as a completed package.

Store code and environment manifests as immutable content. Keep user-editable
`inputs.json`/`parameters.json` outside the immutable payload; the controller
creates a new frozen run plan for each invocation. No required runtime resolver
contacts a package server when executing an offline-complete bundle.

`run.cmd`/`run.sh` locate the bundle relative to themselves and invoke the bundled
controller. They contain no DAG scheduling or scientific algorithm. Standard
options are `--check`, `--inputs`, `--parameters`, `--resume`, `--work-dir`,
`--output-dir`, `--memory` and `--threads`. Preserve original-source readability.

The minimal kernel payload is built from an explicit dependency/resource
manifest and installed package metadata. It cannot be generated by naively
copying the whole source tree or only following static `import` statements.
Dynamic SDK/operator resources are included through the library resource
manifest. Import-time side effects are not used to discover operators.

Package identity includes implementation/environment/codecs/kernel behavior;
cache reuse requires the existing explicit eligibility contract. Cache misses or
verification failure must not silently reuse stale outputs. Scratch lives under
the run's independent partition; preserve enough committed metadata to resume
without keeping every spill file forever.

Full support means every required node/boundary is either represented or
reported as a blocker. Do not drop unsupported nodes, replace a native algorithm
with a toy implementation, or silently collapse a mixed-OS route to one OS.
Cluster deployment exports are labelled separately from single-machine offline
packages and contain endpoint references, never credentials.

## 14. YAML and API compatibility

The new authoring format is `operon.workflow`, schema version 2. Freeze this
top-level vocabulary: `format`, `schema_version`, `params_file`, `inputs_file`,
`environments_file`, `processes`, `workflow`, `profiles`. No arbitrary top-level
keys. `processes` define runner/operator binding, typed inputs/outputs,
environment reference and resources; `workflow` contains `take`, `steps`, `emit`.

References are objects (`{ref: node.port}`, `{param: name}`, `{input: name}`),
not `${...}` expressions. Process invocation uses typed argv tokens. Profiles
contain executor/target/resource/storage defaults; CLI values override selected
profile values, which override workflow defaults. One selected profile is
supported initially; do not invent ambiguous multi-profile merge precedence.

Inline parameter defaults may be extracted only during initial import/save.
Subsequent compilation resolves actual values from the independent parameter
file. Export never overwrites them with current operator defaults.

Old YAML and graph JSON import through a dedicated compatibility normalizer.
Generate one canonical v2 export and retain the requested legacy export where
it is lossless. A required feature unavailable in an older target is an error,
not a dropped field. UI coordinates live in optional `ui.json`.

This phase does not import arbitrary `.nf`. Nextflow-style concepts and CLI
flags are supported through documented examples. Direct Nextflow execution is
a separately scoped adapter; a future DSL subset converter needs an explicit
grammar and fixtures before implementation.

Existing HTTP/CLI/MCP entry points delegate to the same services. New operations
are asynchronous receipts where work may outlive an HTTP request. Progress uses
the durable event cursor and existing polling; HTTP may provide SSE over the
same events. Slow subscribers have bounded buffers and reconnect by cursor;
they cannot block commits. No second WebSocket-only state store.

Errors contain `code`, `message`, `details`, `request_id`, `retry_after` when
applicable and `next_actions`. Reuse existing codes for queue/full/unavailable/
uncertain states. Add specific codes for unsupported boundaries/targets,
environment generation unavailable, expired browsing cursor and unknown remote
submission. Do not encode machine behavior by parsing localized error prose.

## 15. Configuration and overload policy

All service limits are positive typed configuration values, reported in status.
Preserve current user memory settings and the startup snapshot ceiling. New
defaults are engineering starting points, not hidden scientific restrictions.

| Configuration | Initial policy |
| --- | --- |
| Host request handlers | 32, retaining existing implementation |
| Reject I/O handlers | 4; if exhausted close the connection promptly |
| Principal control rate/burst | Existing local patch: 20/s and 40, separate lifecycle lane |
| Principal concurrent dispatch | 8, plus reserved cancellation/status service capacity |
| Queued/active run and retained receipt limits | Carry existing configurable admission policy; resolve replay before quotas |
| Cluster DB/SSH executor workers | 8 each, bounded before submission |
| Per-pass candidate units / hosts | 256 units / at most 4 admission attempts per unit |
| Browse/transfer concurrency | Separate pools; default 2 listings and 2 transfers per principal |
| Event/log pages | Paginated and size-bounded; no full historical log in a status response |

Keep existing frame compatibility during migration. New API requests reference
uploaded immutable plans instead of repeatedly transmitting huge graphs. Report
frame and plan limits separately from data-transfer policy. Count decoded
request lifetime as well as raw body buffers when bounding memory; releasing a
byte budget immediately after reading while retaining a large parsed object is
not full memory accounting.

Bound parse depth, mapping/list cardinality and expanded route node count before
expensive validation/compilation. Estimate and account for retained decoded
objects until dispatch finishes; calibrate the multiplier against measured peak
memory. When a limit is reached, reject with the effective limit and remedy,
never truncate a graph or scientific dataset.

Database/WAL watermarks reject new admissions but allow essential cancellation,
completion and recovery to consume a separately reserved margin. They are not
absolute disk quotas. Events/logs have retention/rotation policies, with truncation
explicitly reported. Do not delete idempotency receipts to free space without a
published replay-window policy and tombstone semantics.

## 16. Delivery units and executable gates

| Unit | Implement exactly this | Required proof before proceeding |
| --- | --- | --- |
| K00 | Protected integration worktree, selective fixes, runtime/dependency manifests and import-boundary baseline | Author fixes and local maintenance/admission regressions; no library code changes |
| K01 | Strict models, schemas, canonical fixtures and compiler to RunPlan | Old/new graph fixtures; identical frozen values and deterministic identities; no scientific imports |
| K02 | Invocation ABI and Context bridge using existing supervisor | Real native Reader/PCA/report parity; info/axis/memory/logs/cancel preserved |
| K03 | Immutable environment preparation, binding, lease and crash recovery | Build/publish crash points; live orphan worker blocks GC; old generation continues while new one prepares |
| K04 | Multi-language boundary codecs and adapters | Real Python -> R -> native executable -> Python branch/join; conflict and ABI split cases |
| K05 | Portable collector/build/verify and minimal kernel | Relocated offline Windows/Linux execution; missing resources block, never omit; no global profile modification |
| K06 | YAML v2 and shared CLI/API/MCP operations | Canvas/YAML round trips, strict negative fixtures, frozen defaults and machine-readable errors |
| K07 | Storage references, bounded browse and jump-host transport | Real SFTP storage-only host; actual bastion route; large directory cancellation and preview limits |
| K08 | PostgreSQL cluster repository and persistent controller | Transaction/idempotency/quotas/outbox fault tests against real PostgreSQL, not SQLite emulation |
| K09 | SSH placement with host receipts and reconciliation | Two compute hosts; lost response, disconnect, restart and no duplicate execution/capacity |
| K10 | Slurm executor | Real scheduler pending/run/cancel/accounting-delay reconciliation; no host-global pool inside allocation |
| K11 | Product integration and mixed target/export coverage | Human and agent submission/status/cancel/result flow; equivalent scientific results |
| K12 | Packaging/release preparation | Exact Windows Setup and Linux package acceptance; publish only after required real-platform gates |

K04/K05 must not wait for a cluster implementation. K07 depends on stable storage
contracts; K08/K09 depend on state/attempt semantics. Keep commits reviewable and
tests specific to each delivered behavior. The coding model must not create a
large scaffold with all tests mocked and label all K units complete.

### 16.1 Required test files/fixtures

Use the existing pytest/native Setup tooling; add these focused suites:

- `tests/test_run_plan_contract.py`: schema, hash vectors, frozen values,
  nested routes, converter ambiguity, negative malformed/oversized input.
- `tests/test_invocation_context.py`: native execution parity, cross-interpreter
  Context, named outputs, logs and process-tree cancellation.
- `tests/test_environment_generations.py`: preparation state/crash matrix,
  lease/GC races, relocated runtime and DLL/resource verification.
- `tests/test_multilanguage_execution.py`: real language/tool fixtures and
  unsupported boundary failures; record skips as missing acceptance.
- `tests/test_standalone_export.py`: extend current tests, retain old fixture
  evidence, and add real relocated/air-gapped target acceptance scripts.
- `tests/test_storage_browse.py`, `tests/test_ssh_jump.py`: bounded directory
  traversal, expired cursor, symlink policy, two-hop key validation and cancel.
- `tests/test_cluster_repository.py`: real PostgreSQL transactions, concurrent
  same-key submissions, rollback versus unknown commit, quota correctness.
- `tests/test_cluster_recovery.py`: reply lost after host acceptance, controller
  restart, node loss with surviving process, fencing and reconciliation.
- `tests/test_slurm_executor.py`: command/parse fixtures plus separate real
  Slurm acceptance; mocked subprocesses cannot satisfy K10.

Keep existing memory/spill/supervisor/queue/Setup tests. Define scientific parity
per fixture (exact identity where appropriate, tolerances otherwise), not one
universal floating-point equality rule. Route data and reference resources in
tests must be synthetic or redistributable, with their provenance recorded.

### 16.2 Performance measurements

Capture a K00 baseline on recorded hardware/runtime, then compare identical
workloads: 16 clients mixing status/events/submit/cancel, slow browse/transfer,
small and large graphs, environment probing and sustained queued work. Record
p50/p95/p99, writer wait/hold, decoded request memory, queue growth, RSS and
scientific throughput. Warm/cold results are separate.

Acceptance requires no unbounded memory/queue/thread growth, prompt cancellation
under overload, no capacity overcommit and no hidden fallback allocator. A
repeatable >20% control-tail-latency regression on the same workload requires
explanation and remediation before rollout. Absolute user-facing latency targets
are set from the recorded baseline, not guessed into timing-sensitive unit tests.

## 17. Review rules and forbidden shortcuts

Each K unit's report contains modified boundaries, tests actually executed,
fault cases, platform evidence and remaining limitations. Module/unit tests,
product integration and real end-to-end acceptance stay separate columns.

Reject an implementation that:

- imports every operator to build a registry or export plan;
- implements a second local scheduler in CLI, export, HTTP or a worker;
- loses frozen values or uses current library defaults during replay;
- treats no heartbeat, no log output or a lost response as confirmed failure;
- clears pins to make an immutable run/package load against different code;
- copies all Form data into RAM at every environment boundary;
- silently downloads dependencies when running an offline package;
- sends scientific files through JSON or through the desktop unnecessarily;
- starts another worker after an uncertain durable submission;
- mutates a running environment generation, or releases a lease on TTL alone;
- adopts global Python processes or removes data outside manifest-owned paths;
- labels mocks, skipped Linux/Slurm tests or a generated archive as E2E success.

## 18. Technical references

These support technology behavior, not claims of Operon implementation:

- [Pydantic strict validation](https://pydantic.dev/docs/validation/latest/concepts/strict_mode/).
- [psycopg connection pools](https://www.psycopg.org/psycopg3/docs/advanced/pool.html)
  and [PostgreSQL explicit locking](https://www.postgresql.org/docs/17/explicit-locking.html).
- [Python packaging compatibility tags](https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/).
- [pip-tools locking](https://pip-tools.pypa.io/en/stable/),
  [renv](https://rstudio.github.io/renv/articles/renv.html), and
  [conda-pack relocation](https://conda.github.io/conda-pack/).
- [Slurm submission and data-staging boundaries](https://slurm.schedmd.com/sbatch.html).

The runtime/library/tool locks, platform qualification and execution evidence
must be produced during implementation. This document fixes the choices and
proof obligations; it does not substitute for that work.
