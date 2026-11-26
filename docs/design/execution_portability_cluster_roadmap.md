# Execution portability, workflow authoring and cluster roadmap

Date: 2026-11-14. Status: **proposal based on inspected source, not delivered
functionality or runtime acceptance**. This document defines the next application
work. It does not authorize a release, a library rewrite, or paid infrastructure.

The subsequent [backend implementation contract](backend_implementation_contract.md)
fixes the technology choices, interfaces, ownership and acceptance gates in this
roadmap. Use [the coding instructions](backend_coding_instructions.md) for
implementation; the contract takes precedence over tentative sketches here.

## 1. Baseline and decisions

The refreshed upstream baseline is application **5.1.9**, commit
`600eed6f53b6db01f7391f408ade1e950d8679b3` in `lovegavin/Operon`. It supersedes
the 5.1.8 snapshot in the upstream comparison, which is in the git history.
The local application checkout remains on `fix/3.0.1-installation`, committed
HEAD `0f2c87cde64700ef1cbbc4a460884b81f19d4162`, with uncommitted Setup,
admission-control and standalone-export work. Preserve those changes when
preparing a separate integration checkout; do not reset this working tree.

The intended product is one analysis engine with visual, YAML, CLI and agent
interfaces. A portable export is another deployment of its execution contract,
not an independently implemented analysis engine. Application and library
artifacts remain separately versioned and updateable.

Decisions:

1. Compile all authoring interfaces to a common immutable run plan.
2. Separate language invocation, environment preparation, data transport,
   execution placement and result publication.
3. Produce target-specific Windows/Linux runnable directories or archives with
   actual runtimes. Launch scripts are small, readable entry points.
4. Align YAML concepts and terminal ergonomics with Nextflow. Do not call YAML
   a Nextflow DSL implementation or claim arbitrary `.nf` conversion.
5. Extend the existing remote file picker into a file explorer and add explicit
   jump-host routing and storage identities.
6. Use Slurm where the site already has Slurm. Offer a separate small-cluster
   SSH mode when no site scheduler exists. Keep one resource authority per host.
7. Migrate the desktop shell to Tauri after these service contracts stabilize.
   Keep React and the scientific Python/R/native execution ecosystem.

## 2. What exists, and what is missing

| Area | Inspected implementation | Remaining work |
| --- | --- | --- |
| Standalone export upstream | `operon/portable.py`: restricted file-based Python scripts with a prepared runtime | Native operators/Readers, routes, converters, conflicting environments and real R/C/C++ support |
| Local export candidate | `biopipe/standalone.py`: native Reader/PCA/plot/summary slice; documented relocated Windows acceptance | Port to current application/library contracts; complete language/environment and platform matrix |
| Remote files | `RemoteFilePicker`, `/api/remote/{id}/browse`, server-side listing, parent/hidden-file controls and paging | Persistent explorer, bounded huge-directory browsing, storage-only access and reusable data locations |
| Remote execution | Multiple SSH profiles and local/SSH target assignment, auto/manual placement | Generic bastion chains, cluster inventory, persistent cross-host placement and Slurm integration |
| Resource pools | Durable host/account pool with worker supervision and memory control | Cross-host coordination; current host pools do not form one distributed allocator |
| Environments | Dedicated Python environments and environment metadata | Common invocation/Context behavior across environments; immutable prepared generations; portable non-Python closures |
| YAML | Strict static workflow parser and independent parameter/execution JSON | Nextflow-oriented authoring model, profiles and explicitly supported interoperability |
| Desktop | React/React Flow in the existing desktop WebView host | Later Tauri shell and process-lifecycle migration |

Source details that affect the design:

- The current remote `browse` handler enumerates and sorts the entire directory
  before returning a 200-entry slice. UI paging alone does not bound server work.
- The SSH client does not currently pass a tunneled socket to Paramiko. Its
  optional interactive gateway menu is not general `ProxyJump` support.
- The environment bridge wraps a Step with `supports_streaming = False`, writes
  Form data through NumPy files and loads its result in the parent. It must not
  become the universal high-volume or streaming transport without further work.
- Editable workflows currently follow the installed native library in places
  where old pins are cleared. Preserve editing convenience, but freeze exact
  implementations for accepted runs and exported packages.
- Upstream version metadata needs reconciliation: the latest commit/library
  packaging says 0.1.1, while `library/release.json` still records 0.1.0 and a
  5.0.0 build application. Do not infer a verified asset identity from either
  label alone. The library maintainer owns library metadata corrections.

The previous standalone export contract (in the git history) remains useful. This roadmap extends it to current upstream, multiple environments and
cluster deployment; it does not expand its existing acceptance claims.

## 3. Preserve the author's fixes and local repairs

Port by behavior and regression test, not by copying whole old modules over new
ones. Retain current namespaces, builder and manifest contracts.

| Change family | Required preservation |
| --- | --- |
| Windows environment preparation | UTF-8 probes; correct DLL search paths; no probe working directory inside the directory being replaced; install-state coordination; retry and rollback on commit failure |
| Scientific resources | Vendored PDBFixer Python/XML/template resources and `resources.json`; generalize resource collection, not a one-off exporter filename list |
| Library delivery | Builder-generated identities and checksums; ordinary base-library installation; non-conflicting independent library installation |
| Task and agent behavior | Native result links; task directory conventions; current CLI/API/MCP capabilities and on-demand metadata discovery |
| Local Setup repairs | Installation maintenance blocks replacement workers from restarting while update/uninstall drains owned processes; clear ownership and graceful cleanup |
| Local control-plane repairs | Bounded request handling/rejection, durable-queue admission limits and principal accounting |
| Local standalone candidate | Shared application export service, native scientific parity, relocation and offline acceptance evidence |

A fix may need a new implementation after the namespace and environment changes.
Carry its regression scenario forward even when its original patch cannot apply.

## 4. Common execution contracts

```text
Canvas / YAML / CLI / MCP / supported Nextflow import
                         |
                    WorkflowSpec
                         |
              validate + resolve + freeze
                         |
                      RunPlan
              /          |            \
      local executor  remote executor  package builder
              \          |            /
                 Invocation adapters
             Python / R / shell / native
                         |
              artifacts + logs + checkpoints
```

Use versioned JSON-serializable records with published schemas:

| Contract | Contents and responsibility |
| --- | --- |
| `WorkflowSpec` | Editable node/edge definitions, port references and parameter-file references; UI positions remain optional metadata |
| `RunPlan` | Expanded route graph, explicit conversions, frozen values, resolved implementations/resources/environments, placement constraints and immutable input identities |
| `InvocationSpec` | Runner kind, entry point, named inputs/outputs, argument array, parameter JSON, working directory, environment reference and required execution capabilities |
| `EnvironmentSpec` | OS/architecture/ABI, interpreter/tool requirements, dependency lock, runtime resources, model assets, build recipe and content identity |
| `ArtifactRef` / `StorageRef` | Logical identity, representation, location, ownership/lifetime, size and verification state; storage locations are not interchangeable filesystem strings |
| `AttemptRecord` | Stable run/unit/attempt identity, execution receipt, resource lease, logs, checkpoint/publication state and confirmed process-tree exit |

Keep SDK v3 / revision 3.7 port declarations and existing operator entry points.
Introduce execution-adapter and bundle schema versions independently. Operators
do not need to rewrite their scientific code or describe cluster scheduling.
Optional explicit runner/resource metadata can be normalized by the builder;
unknown dynamic requirements block a complete export rather than being guessed.

Saved parameter values remain in independent JSON. Import uses the imported
values as defaults; a later library-default change does not modify them. Freeze
the resolved invocation values for each run. Keep `declaration_sha` for audit,
but do not make documentation/default-only edits change code identity.

Revalidation is selective: graph/parameter/environment/target changes invalidate
affected checks. File validation and dependency readiness remain separate.
Successful dependency readiness may be reused only for the same environment
generation and requirements, not an arbitrary mutable interpreter path.

## 5. Complete, modular standalone export

### 5.1 Deliverable and package structure

The primary deliverable is an inspectable analysis package runnable without an
installed Operon application, profile, registry service or pool daemon.

```text
analysis-package/
  run.cmd                         # Windows entry point, when this target exists
  run.sh                          # Linux entry point, when this target exists
  workflow.yaml
  parameters.json                 # editable values, initialized from saved values
  inputs.json                     # editable input locations
  package.json                    # platform requirements, capabilities, checksums
  plan/run-plan.json              # original frozen plan
  plan/implementation-lock.json
  controller/                    # minimal runtime and shared execution kernel
  steps/<implementation-id>/     # original source, declarations and resources
  converters/<converter-id>/
  environments/<content-id>/     # actual target runtime/dependency closure
  licenses/
  verification/
  work/<run-id>/                  # per-run scratch, spill and durable checkpoints
  results/<run-id>/               # committed artifacts and provenance
```

Do not package the GUI/API server as a substitute for a minimal execution
kernel. Do not translate every analysis into newly generated Python. Original
operator code and shared execution semantics must be reused.

BAT/CMD/SH only locate the package, invoke its controller, forward arguments and
return its exit code. The controller owns DAG scheduling, resume, cancellation,
memory leases, retries and publication. Avoid deeply nested shell commands.

Editing `parameters.json` creates a new resolved run identity and invalidates
affected checkpoints. Keep the original frozen plan for audit. Code edits are
detectable and require an explicit updated lock; do not reuse old results after
an unrecorded code or environment change.

### 5.2 Language adapters

| Execution kind | Packaging and invocation |
| --- | --- |
| Native Python/SDK operator | Original module + SDK/Form/Context execution kernel; structured invocation and owned worker process |
| Python script | Source plus generated boundary adapter; prepared interpreter; inputs/parameters via explicit files/arguments |
| R | Original R source, target R runtime, locked packages and required native libraries; `Rscript` adapter |
| Shell/external program | Original script/tool and declared resources; an actual compatible shell/toolchain, with structured outer invocation |
| C/C++ | Build for the selected target during packaging; carry executable/shared libraries, source and build recipe; do not require a compiler on the recipient machine |
| Route operator | Expand the pinned inner graph and preserve outer port/parameter mapping; do not turn it into an opaque downloaded dependency |
| Converter | Include the resolved converter implementation and its environment; expose it in the plan and provenance |

The adapter contract covers input/output validation, progress/log events,
timeouts, cancellation, retries, exit codes, artifacts and resource use. A native
operator in a dedicated interpreter must receive equivalent Context behavior;
it must not silently lose memory control, logging or file ownership.

Static import inspection discovers candidates, not a complete dependency
closure. Dynamic imports, external tools, bundled templates and model weights
need declared resources or concrete build verification. Generalize the current
resource manifest so PDBFixer-style files survive every packaging path.

### 5.3 Environment resolution

Resolve one compatible dependency closure where possible. Split conflicts into
isolated process invocations and private dependency directories. Reuse one
Python executable when interpreter/ABI compatibility permits; ship additional
interpreters only when different Python versions or binary compatibility require
them. Do not rewrite dependency import names by string replacement.

R and native tools have their own closures. Deduplicate identical prepared
environments by content identity in the build cache. The exported tree must not
depend on external cache symlinks or another installation directory.

Prepare a new environment generation in staging, verify it and atomically
publish it. Attempts pin a generation until their process tree exits. Repair
builds a new generation rather than changing files under a running process.
Preserve existing installation rollback and maintenance protections during this
transition; garbage collection requires zero references and confirmed process
exit. A mutable interpreter directory cannot provide this guarantee by itself.

Do not copy an arbitrary Conda directory and assume relocation. Each builder
must handle prefixes, launchers, shared libraries and target probes explicitly.
Windows and Linux artifacts are built and tested separately. A Linux-only
workflow may be exported from Windows using an authorized Linux build host, but
the resulting package is still a Linux package.

Native offline-complete packages carry actual runtime files, not only pip/Conda
requirements. Optional OCI/Apptainer delivery is useful for Linux/HPC dependency
closures, but explicitly requires a compatible container runtime on the target.
Host kernel, CPU features and GPU drivers remain declared prerequisites. Check
redistribution rights; unavailable licensed tools or required model assets are
specific blockers, not silently omitted payloads.

### 5.4 Data, memory and recovery

Use explicit representation adapters: file references, JSON metadata, existing
Form-compatible disk representations, NumPy/memory-mapped arrays or other
declared table formats. Chunked transfer is allowed only where both producer and
consumer support it. Never infer biological meaning or silently turn a matrix
into a list/table with unspecified axis semantics.

Cross-process handoff is an owned artifact or bounded channel, not an arbitrary
pickle or an unbudgeted full copy. Account for producer, conversion, transport
and consumer overlap. Preserve spill partitions, per-run scratch quotas and
emergency spill. Existing full-mode operators remain full-mode.

Standalone resume uses committed stage checkpoints, verified inputs/code/
parameters/environment and eligible cache declarations. A missing or modified
artifact invalidates the checkpoint. Non-deterministic/external-side-effect
steps are not automatically reusable. Cancellation confirms the entire owned
process tree stopped before resources are released.

### 5.5 Meaning of complete export

Keep separate `built`, `verified`, `execution_verified` and `offline_complete`
states from the earlier export contract. A package must cover every required
node and edge, or return a node-specific blocker report.

A mixed Windows/Linux route is not automatically a single-host package. Offer:

- a single-target export after verifying all steps support that target; or
- a cluster deployment package retaining placement, external server bindings
  and declared infrastructure requirements.

The second kind is not an offline single-computer package. Never include SSH
credentials in either deliverable. External user datasets may be referenced or
explicitly included; do not silently copy an entire local/server data directory.

## 6. Nextflow-oriented YAML and terminal workflow

Nextflow uses its own DSL, not YAML. Align concepts and daily operations rather
than advertising byte-for-byte syntax compatibility.

| Familiar concept | Operon design |
| --- | --- |
| `process` | Named invocation definition: inputs, outputs, runner, environment and resources |
| `workflow`, `take`, `emit` | Named graph/module with explicit input and output port mappings |
| `params` | Parameter schema/references; actual saved values remain independent JSON |
| `path`, `val`, `tuple` | Typed file/value/record boundaries, validated against port format contracts |
| `cpus`, `memory`, `time` | Normalized resource requests and limits in the execution plan |
| `profiles` | Local, SSH, Slurm and container/environment configurations |
| `executor` | Runtime placement adapter; scientific code remains unchanged |
| resume and result publication | Existing durable stage checkpoints, eligible reuse and native output routing |

Design sketch only; not current accepted syntax:

```yaml
format: operon.workflow
schema_version: 2
params_file: parameters.json
processes:
  QC:
    runner: command
    environment: fastp
    input: {reads: {type: path, format: fastq}}
    output: {report: {type: path, format: json}}
    resources: {cpus: 4, memory: 2GiB}
    command:
      argv: [fastp, -i, {input: reads}, --json, {output: report}]
workflow:
  take: {reads: {type: path, format: fastq}}
  steps:
    qc:
      process: QC
      in: {reads: {ref: workflow.reads}}
      out: {report: report.json}
  emit: {report: {ref: qc.report}}
profiles:
  local: {executor: local}
  cluster: {executor: slurm, cluster: lab}
```

Preserve arbitrary typed JSON values and explicit references; do not evaluate
embedded Python/Groovy during import or validation. Resolve output paths within
the attempt directory and detect overlapping writes. Environment declarations
live in a separate lock/spec; the small example does not contain a full bundle.

The exact spelling is finalized after a parser/round-trip prototype. Keep the
existing YAML importer, provide explicit schema migration, and make canonical
export conform to the selected schema. A GUI -> YAML -> GUI round trip must
preserve ports, converters, nested routes, parameters and execution settings;
unrepresentable edits produce a diagnostic rather than disappearing.

Proposed terminal experience:

```text
operon validate main.yaml --profile cluster --params-file parameters.json
operon environment prepare main.yaml --profile cluster
operon run main.yaml --profile cluster --params-file parameters.json
operon run main.yaml --profile cluster --resume RUN_ID
operon export main.yaml --target linux-x86_64 --format standalone
```

Reuse existing CLI operations and compatibility aliases where possible. Return
stable machine-readable errors as well as readable progress; dependency
installation remains explicit. GUI, CLI and agent calls use the same service.

Nextflow interoperability is three distinct capabilities:

1. **Conceptual/CLI alignment:** the first deliverable, with mapping examples.
2. **Static DSL2 subset import/export:** fixed processes/ports/graphs with a
   documented support matrix. Unsupported channel operations, dynamic code,
   plugins or configuration report source locations and reasons. Never use
   regex to pretend arbitrary Groovy is a static DAG.
3. **Existing project execution:** optionally run an unchanged Nextflow project
   through a Nextflow adapter. Prepare its Java/Nextflow requirements explicitly.
   Treat the project as one externally orchestrated route with its own state;
   this does not provide editable internal canvas nodes automatically.

Sample channels and in-memory data chunks are different abstractions. For native
batch workflows, define bounded scatter and explicit keyed joins/zip/cartesian
operations; preserve sample identity. A sample-level dataflow graph does not
make a full-reading Reader stream its contents.

## 7. Local remote-file explorer

Extend the current picker into a reusable Files panel, accessible from input
ports and server settings. Keep the quick picker for simple selection.

- Server/storage selector, breadcrumbs, lazy folder tree, virtualized file list,
  bookmarks, hidden-file toggle and cancelable bounded search.
- Metadata columns from `stat`; directory size is unknown unless explicitly
  calculated. File size never requires full reading/decompression.
- Drag a remote file into the canvas to create a server-bound input reference.
  Selecting a file does not download it to the desktop.
- Text/table previews have byte/row/time caps. Binary formats use available
  metadata/thumbnail adapters; never load a whole FASTQ/BAM merely to preview.
- Expose transfer progress, resumable transfer and completed-file reuse through
  the existing transfer service. Prefer shared storage or server-to-server
  transfer instead of relaying scientific data through the desktop.
- Use stable storage IDs plus paths relative to configured roots; mount mappings
  tell each compute host how that storage is visible. Same path strings on two
  servers do not establish that the data is shared.
- Read-only browsing works through SFTP even on a storage-only server without
  Operon/Python. Rich scientific previews can use an optional server service.
- Server browsing enforces the SSH account/root policy and bounded concurrent
  requests. Start with read-only UI; destructive file operations are a separate
  explicit feature, not a prerequisite for browsing.
- Huge directories use bounded enumeration/cursors or an explicitly built
  index. Full global sorting may require indexing; do not promise instant global
  sorted paging while re-enumerating the entire directory for every page.
- Human/agent selection events carry the storage reference and revision, making
  remote inputs inspectable through the same collaboration APIs.

## 8. Bastion and cluster architecture

### 8.1 Current answer and target topology

Current source supports independent SSH targets and per-step placement. It does
**not** yet implement general jump-host chains or a persistent multi-host cluster
resource allocator. No Slurm executor was found in the inspected source.

```text
Windows UI / CLI / agent
          |
     SSH bastion               (authentication/tunnel, not assumed compute)
          |
  persistent control service   (may be a separate machine)
       /                 \
  SSH executor         Slurm executor
    /    \                   |
 host A  host B          Slurm allocations
 pool    pool          on compute nodes
    \      \              /
       storage endpoints
       shared FS / SFTP
```

Keep gateway, controller, compute and storage roles distinct. A bastion is not
automatically permitted to run daemons, install scientific environments or hold
large datasets. Its SSH forwarding policy determines whether tunneled access
is possible. One server can have multiple roles when explicitly configured.

### 8.2 Transport and deployment

Extend Paramiko with `direct-tcpip` channels passed as `SSHClient.connect(sock=)`
and explicit hop profiles. Support normal OpenSSH ProxyJump-style configuration
concepts; do not run arbitrary shell proxy commands by default. Check host keys
and authenticate each hop. Secrets remain in credential storage, not workflow
YAML, exported packages or log records. Agent forwarding is not required.

Inventory records node IDs, SSH routes, roles, OS/architecture, resource labels,
GPU capabilities, scratch roots, storage mappings and execution capabilities.
Deployment is explicit and resumable; upload a versioned server package once,
then handshake against protocol/capability/library/environment manifests.
Subsequent clients reuse compatible installations. Check only the selected
workflow's required operators/environments instead of scanning every package on
every connection. Incompatible capabilities give actionable preparation steps.

The persistent server control service owns accepted work. A desktop disconnect,
closed file browser or expired UI session does not stop jobs. Connections
subscribe to events and recover through durable run/attempt IDs.

### 8.3 Two execution modes

**Existing HPC scheduler: Slurm first.** Submit through `sbatch`, observe through
`squeue`/`sacct`, cancel through `scancel`, and persist scheduler job IDs and
submission receipts. Slurm owns cluster CPU/RAM/GPU allocation, queues and site
fair-share policy. Operon owns workflow dependencies, environments, data staging,
scientific execution and artifact publication.

Do not run a host-global Operon allocator on the login node or reserve resources
outside Slurm allocations. A worker inside an allocation receives a budget no
larger than that allocation/cgroup and may schedule its own steps within it.
Slurm submission does not stage the workflow's data automatically: storage
visibility and transfer dependencies remain explicit.

**Small cluster without a scheduler: SSH host pools.** A persistent placement
service selects a host, and that host's existing pool makes the final atomic
admission decision. There is exactly one physical capacity ledger per host/
account/control domain. The controller must not grant a second independent RAM
budget beside the host pool. Add CPU/GPU/scratch capacity and transfer slots to
placement constraints without inventing distributed shared memory.

Scheduling first filters hard requirements (OS/ABI, environment, GPU, accessible
data and user constraints). Rank feasible hosts using bounded estimates of queue
wait + data transfer + runtime, with aging/fairness. Cache prepared environments
and prefer data locality. Estimates are heuristics, not a globally optimal
schedule. A route operator stays on one execution target by default, matching
the existing user-facing constraint.

Read capacity at host-pool startup or an explicit capacity-generation update.
Dynamic admission uses the resource ledger and actual task observations; do not
replan every stage from fluctuating free RAM. OS pressure triggers existing
emergency spill and containment inside the granted budget. A single process
cannot combine the RAM of two hosts.

### 8.4 State, failures and limits

Keep host SQLite WAL databases on local disks. Never place one WAL database on
NFS and call it a distributed pool. For the persistent cluster service, use a
PostgreSQL-backed metadata store when implementing multi-host coordination;
keep SQLite available for standalone/local operation. Both implementations
follow tested request/attempt/event semantics through a store interface.

Start with one cluster controller; PostgreSQL alone does not create active-active
HA. Controller failover later requires leadership/fencing and recovery tests.
Worker/node heartbeat loss means unknown execution state, not confirmed death.
Reconcile or fence an old attempt before a replacement can execute.

Retain atomic idempotency keys, lost-response lookup, durable submission
receipts, transactional outbox, process-tree ownership, artifact commit and
resource-release phases. For scheduler submission without a response, reconcile
using a stable submission token/job metadata before retrying.

Bound requests, queued jobs, metadata bytes, event retention, transfer buffers,
temporary storage and per-principal usage. Reject overload before persisting a
large new request. Avoid a synchronous busy-response drain in the accept loop.
Measure tail latency under real submission/query/transfer load before deciding
whether an async transport or a Rust hot path is justified.

Credentials and principal mappings must reflect the site's trust model. Same-OS-
account pool tokens are not isolation between hostile users. Multi-user cluster
deployment should preserve per-user SSH/Slurm identities or use administrator-
managed service authorization; a client-provided principal string cannot grant
another user's privileges or quota.

Cross-host edges initially exchange committed artifacts with checksums,
reference-counted retention and resumable transfer. Existing bounded in-host
streaming remains available where declared. Network streaming/fan-out across
hosts is a separate later feature with its own backpressure and recovery design.

## 9. Technology choices

| Layer | Choice | Rationale/boundary |
| --- | --- | --- |
| UI and workflow canvas | Existing React + TypeScript + React Flow | Preserve current interaction and operator ecosystem |
| Authoring/contracts | Existing strict YAML parser + versioned JSON Schema and typed Python records | Safe static compilation; no second task engine |
| Scientific execution | Python control kernel, native Python/R/shell/compiled-tool adapters | Reuse code, memory management and original analysis behavior |
| Environment builds | Existing explicit builders extended with immutable generations and target-specific locks/resources | Actual relocatable files and verified dependency closures |
| Linux container option | OCI / Apptainer adapter | Useful on HPC; optional, target runtime requirements explicit |
| SSH/files | Existing Paramiko with tunneled sockets and SFTP | Reuse established transport and support storage-only endpoints |
| Local state | SQLite WAL on local disks | Preserve durable host-pool behavior |
| Cluster state | PostgreSQL behind the cluster service | Central transactional metadata; not direct client DB access or automatic HA |
| HPC scheduling | Slurm executor | Reuse existing site allocation and queue policy |
| Small SSH cluster | Persistent placement service + existing host pools | Reuse atomic per-host admission; bounded heuristic scheduling |
| Future desktop host | Tauri 2 + Rust shell, existing React UI, packaged management sidecar | Replace the host independently of scientific runtimes |

Do not introduce Kubernetes, Kafka, Ray or Dask as mandatory infrastructure for
ordinary local/HPC use. Reconsider them only for a demonstrated workload whose
requirements exceed the above execution and storage model.

## 10. Tauri migration boundary

Do this after the API, run plan and installation lifecycle stabilize. The first
Tauri release replaces window/menu/dialog/clipboard/drag/drop/tray/credential and
process-lifecycle responsibilities. It reuses the React frontend and versioned
application APIs, and launches the lightweight management service as a sidecar.

Scientific runtimes are prepared on the chosen execution host and do not load at
desktop startup. This separation already belongs in the service architecture;
Tauri does not by itself remove Python scientific dependencies or make a full
environment tiny. Windows still uses WebView2. Keep the server, CLI and exported
analysis packages independent of the desktop shell.

Use scoped shell/IPC capabilities and owned process handles. Measure cold/warm
startup, idle memory, file-dialog/drag behavior, clipboard permissions, shortcut
launch, upgrade/uninstall and orphan-process behavior against the existing host.
Move CPU-intensive control paths to Rust only when profiling supports it; do not
rewrite tested scientific modules as a prerequisite for a shell migration.

## 11. Delivery order and acceptance gates

| Milestone | Scope | Exit gate |
| --- | --- | --- |
| M0: protected baseline | New integration checkout from pinned 5.1.9; selective local repairs; reconcile build/manifests with library maintainer | Targeted regressions for author fixes, Setup maintenance, admission limits and library/resource identity |
| M1: execution contracts | Frozen RunPlan, InvocationSpec, common environment/Context adapter and package plan | Same native route behaves identically via desktop service, CLI and packaged runner; no silent loss of memory/logging semantics |
| M2: complete export | Python/R/native tools, conflicting closures, converters, nested graphs, target builds and offline contents | Real relocated Windows and Linux mixed-language workflows; no installed Operon/system interpreter dependency |
| M3: authoring experience | Nextflow-oriented YAML/profile model, migration and CLI examples; supported interoperability scoped separately | Canvas/YAML round trips and frozen-value checks; unsupported DSL constructs rejected without executing import code |
| M4: remote explorer and transport | Reusable Files panel, storage references, bounded enumeration, bastion chains | Actual access through a bastion to compute/storage endpoints; huge-directory cancellation; no implicit download |
| M5a: HPC execution | Slurm profile, data staging, receipts/cancel/recovery and allocation budgets | Real scheduler queue/run/cancel/reconnect tests and equivalent scientific results |
| M5b: small-cluster execution | Persistent cluster service, PostgreSQL state and host-pool admission | Two compute hosts and one storage endpoint; concurrent clients, fault/recovery and quota verification |
| M6: Tauri shell | Native host replacement using stable service APIs | Real Windows install/shortcut/update/uninstall and human/agent interaction acceptance; server/CLI remain headless |

M2 and M3 share M1 contracts. M4's browsing work can develop independently once
StorageRef is stable. Do not delay ready fixes until all cluster/Tauri work is
complete; publish coherent increments with capability-negotiated interfaces.
Assign the next application version after integration scope is fixed. Library
updates retain independent versions and releases.

### Required verification matrix

- Compare an original scientific workflow with the exported version, including
  numeric tolerances, output metadata, native figures and branch/join results.
- Execute Python -> R -> C/C++ tool -> Python reporting with a parallel branch;
  include incompatible Python dependency pins and a separate interpreter-version
  case. Test real runtime files, not only mocked launch arguments.
- Test a native Form/Reader route, explicit converter, nested route, multiple
  inputs/outputs, no-output side effects, and a deliberately unsupported export.
- Relocate packages into paths with spaces/non-ASCII characters on clean Windows
  and Linux targets. Disable network and clear external runtime lookup for the
  offline claim. Check vendored resources and actual dynamic-library loading.
- Test low memory/spill, full scratch disk, cancellation during a child process,
  corrupt checkpoint, modified input/parameter/environment and partial artifact
  publication. Resume cannot rerun an uncertain side-effecting attempt blindly.
- Verify old YAML import, canonical new YAML export, preserved input port mapping,
  independent execution settings and defaults frozen at import/save time.
- Browse a synthetic large directory over a slow connection with bounded server
  work and client memory; cancel without blocking task status queries.
- Exercise two compute hosts, storage with different mount paths, a genuine
  bastion-only network route, reused uploads and direct/shared-storage transfers.
- Use multiple real clients/principals, connection loss after submission,
  controller restart, worker survival, node loss and explicit fencing/recovery.
  Record CPU/RAM/GPU/scratch leases and control-plane p95/p99 under load.
- Run Slurm tests only on a real available Slurm installation. A subprocess mock
  proves command construction, not cluster execution or site authorization.
- For Tauri, repeat actual double-click/shortcut, drag/select/copy/undo, native
  result viewing, settings persistence, upgrade, normal exit and uninstall.

Record module tests, product integration and real end-to-end acceptance
separately. Unsupported hardware/platforms stay marked unverified. Set measured
performance thresholds during M0 on fixed workloads; do not invent speedup
claims from architecture choices.

## 12. Implementation touchpoints and references

Upstream touchpoints (verify again against the pinned integration checkout):

- `operon/workflow_spec.py`, application/task services and
  `src/web/execution_plan.py`: authoring, frozen plans and target planning.
- `operon/portable.py` plus the local `biopipe/standalone.py` candidate:
  consolidate export planning/build/status through the shared service.
- `operon/environments.py`, worker adapters and `operon/engine/`: resource-aware
  cross-environment invocation, environment leases and process ownership.
- `operon/remote/client.py`, `operon/remote/server.py`,
  `src/web/remote_api.py`, `frontend/src/RemotePanel.tsx`: tunneled transport,
  file browsing and reusable UI.
- `operon_library_builder/descriptors.py`: resource manifests and static
  metadata. Coordinate changes with the independent library-builder boundary.

Primary technical references consulted on 2026-11-14:

- [Nextflow processes](https://docs.seqera.io/nextflow/process),
  [workflows](https://docs.seqera.io/nextflow/workflow),
  [profiles/configuration](https://docs.seqera.io/nextflow/config/), and
  [executors](https://docs.seqera.io/nextflow/executor).
- [Paramiko SSHClient tunneled socket](https://docs.paramiko.org/en/stable/api/client.html)
  and [transport channels](https://docs.paramiko.org/en/stable/api/transport.html);
  [OpenSSH ProxyJump](https://man.openbsd.org/ssh_config#ProxyJump).
- [Slurm overview](https://slurm.schedmd.com/overview.html) and
  [sbatch](https://slurm.schedmd.com/sbatch.html).
- [SQLite WAL deployment constraints](https://sqlite.org/wal.html).
- [Apptainer OCI support](https://apptainer.org/docs/user/latest/docker_and_oci.html)
  and [bind paths](https://apptainer.org/docs/user/latest/bind_paths_and_mounts.html).
- [Tauri process model](https://v2.tauri.app/concept/process-model/) and
  [external binaries/sidecars](https://v2.tauri.app/develop/sidecar/).

The architecture and milestone choices above are project recommendations derived
from the inspected implementation and requirements, not features claimed by
those external projects on Operon's behalf.
