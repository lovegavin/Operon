# K11 plan product adapters

Status: the bounded results slice passed its focused grouped check (53 passed,
3 link-creation skips). This is a product adapter slice, not complete K11 or
real execution acceptance.

| Scope | Implemented | Module/API tests | Real execution | Remaining limits |
| --- | --- | --- | --- | --- |
| Shared plans | Compile, submit, details, cancel and bounded results under `Application.plans` | Focused results/service/state group: 53 passed, 3 skips | Not run by this task | Host executor/platform evidence is owned by the corresponding execution gates |
| HTTP/CLI/MCP | Strict requests, separate read/run permissions, paged attempts/events/artifacts and bounded logs | Durable state ownership/read and adapter/permission cases passed; filesystem link cases skipped | Not run | No frontend plan editor or artifact download/preview adapter |

## One execution owner

`PlanService` compiles through the shared compiler and delegates execution only
to `PoolService.submit_plan/plan_details/plan_cancel` or the equivalent
`plan.submit/plan.details/plan.cancel` RPC. The existing host coordinator,
resource grants and `RunPlanExecutor` own attempts. No allocator, launch loop,
subprocess or fallback execution is implemented in the adapters.

Read-only results use that same owner via `plan.events`, `plan.attempts`,
`plan.artifacts` and `plan.logs`; these RPC methods are not accepted on the
reserved lifecycle listener.

The existing K02 `InvocationRunner` and `Application.run_plan` compatibility path
remain unchanged. They are not silently repurposed for arbitrary multi-unit
plans. An application without an existing shared pool receives
`engine_unavailable` when it submits through the new service.

Compilation returns a canonical RunPlan and does not submit, launch, install or
prepare an environment. Graph compilation uses `Application.compile_plan`.
Authoring-v2 compilation calls the dedicated normalizer with explicit sidecars,
then `WorkflowCompiler.compile_authoring`. Unsupported policies/boundaries remain
compiler errors. The old `workflow_spec.load_workflow` behavior is unchanged.

## Explicit binding and identity

`operon/contracts/plan_operations.py` contains shared strict, frozen models used
by the application/API and host RPC. Bindings declare:

- Workspace-relative `package_root` and `environment_store`.
- `environments`: invocation environment reference to immutable generation ID
  and generation-relative executable.
- `storage`: storage ID to workspace-relative root.
- `inputs`: named file boundary records with workspace-relative path,
  representation, byte size, SHA-256 and explicit metadata.

Absolute/traversing paths, unknown fields and boolean byte quantities are
rejected. Submission verifies the frozen plan identity and required binding
coverage before contacting the host. The host repeats strict binding validation,
confines paths, verifies immutable environment requirements and resolves physical
locations under the registered workspace. A request cannot select another
scheduling principal or another registered workspace through the HTTP body.

`request_id` is mandatory for submission. A timeout, lost response or
`response_unavailable` transport error produces `submission_unknown` with the
original key and `retry_same_request` guidance. The application never makes an
automatic second submission or falls back to a local process. Session setup
failure occurs before submit and is reported separately. Known host rejection
codes, statuses and retry delays are preserved.

## Product entry points

| Entry point | Permission | Behavior |
| --- | --- | --- |
| `POST /api/v1/plans/compile` | context | Graph or authoring-v2 compile only |
| `POST /api/v1/plans` | run | Explicit frozen plan + binding + request ID |
| `GET /api/v1/plans/{run_id}` | context | Compact authoritative state, revision, counts and result location |
| `GET /api/v1/plans/{run_id}/events` | context | Retained transition metadata with integer cursor |
| `GET /api/v1/plans/{run_id}/attempts` | context | Paged owned attempt IDs, states and exit codes |
| `GET /api/v1/plans/{run_id}/artifacts` | context | Paged committed artifact IDs, manifest hashes and byte sizes |
| `GET /api/v1/plans/{run_id}/logs` | context | Bounded bytes from one owned attempt's worker log |
| `POST /api/v1/plans/{run_id}/cancel` | run | Host-authorized coordinator cancellation |

HTTP operations use the existing bounded application dispatcher; details and
cancel use its reserved lifecycle lane. This changes no host scheduling budget.
Disconnecting a client detaches its observation session and does not cancel an
accepted plan. Error envelopes reuse `ContractError` fields and include request
IDs and applicable retry delays. FastAPI publishes all strict models in the
existing versioned OpenAPI schema.

CLI commands are `operon plan compile <workflow-file>`, `submit <plan.json>
--binding <binding.json> --request-id <key>`, `details <run-id>` and `cancel
<run-id>`. Compilation can write `--output <plan.json>`. It accepts graph frozen
`--values`, or authoring-v2 `--parameters`, `--inputs`, `--environments`,
`--profile`, `--initial` and `--require-files`. Authoring sidecars resolve within
the explicitly selected project, and the project must be inside the application
workspace. Values are loaded before connecting; missing sidecars are not replaced
with current defaults. Only explicit `--initial` permits first-import parameter
default extraction. No plan command implicitly requests edit/plugin permission;
only submit/cancel request run permission.

MCP tools `operon_plan_compile`, `operon_plan_submit`, `operon_plan_status` and
`operon_plan_cancel` forward to those same endpoints. Run tools still require the
existing explicit `--allow-run` connection capability. MCP carries neither a
second scheduler nor a filesystem execution path.

## Bounded result observation

`PlanService.events/attempts/artifacts/logs` delegate to the corresponding
`PoolService.plan_*` methods or `plan.*` RPC using the current registered
workspace, scheduling principal and pool session. The host verifies the run's
workspace and principal before the read. A log attempt must belong to that run.
These operations use the normal bounded control/offload lane, leaving the
reserved lifecycle lane available for compact status and cancellation. They do
not instantiate an executor, acquire a scientific resource grant, retry work or
change durable state.

`operon/plan_results.py` projects bounded metadata directly from the existing
StateStore under its lock. Events contain cursor, kind, unit/attempt identity,
revision and timestamp; arbitrary event payloads are omitted. Real attempt
events with a null workspace field remain visible through the authorized run.
Expired cursors produce `cursor_expired` with a retained `floor`; continuing
from that floor explicitly accepts the historical gap. Attempt listing remains
available after event retention removes earlier attempt events.

Events, attempts and artifacts accept `after`, `limit` (1–200, default 100) and
`max_bytes` (2048–65536, default 32768). Each complete page, including its JSON
envelope, stays within the byte budget. Continue using `next_cursor` while
`has_more` is true. Event cursors are integers; attempt/artifact cursors are
opaque strings. The run revision is included for observation. Artifact pages
are a live listing rather than a retained snapshot: refresh from the beginning
after execution changes, and enumerate a terminal run for a complete stable
inventory. Artifact rows include explicit durable resume references and exclude
staging artifacts. They describe committed artifact groups; the hash is the
committed manifest hash, not an individual output file hash. Neither mutable
worker output indexes nor artifact location paths are returned or opened.

Logs require `attempt_id`; `offset` and `next_offset` count raw bytes. The
`max_bytes` range is 1–65536 (default 16384). `encoding=base64` preserves exact
bytes, including UTF-8 characters split across pages; `encoding=text` decodes
UTF-8 with replacement. The response reports `available`, attempt `state`,
`bytes_read`, current `size_bytes` and `eof`. EOF is an observation of the current
file length, not a completion claim. An attempt that has not created its log
returns `available=false`. A now-out-of-range offset produces `plan_log_offset`
with the current size, allowing an explicit restart at zero.

Only the fixed host-owned worker log is addressable, with compatibility for the
previous attempt layout. The reader rejects symlinks, reparse points, hardlinks
and non-regular files; POSIX directory handles and Windows final-handle checks
confine the opened file. Caller paths, receipt paths and worker manifests cannot
select another file. Log content itself is application output and may contain
paths printed by the worker. No artifact download, arbitrary file read, file
preview or attachment relay is introduced. Existing job artifact routes use a
different execution layout and are not reused for invocation plans.

Examples (all require only context permission):

```text
operon plan events <run-id> --after 0 --limit 100 --max-bytes 32768
operon plan attempts <run-id> --limit 100
operon plan logs <run-id> --attempt-id <attempt-id> --offset 0 --max-bytes 16384 --encoding base64
operon plan artifacts <run-id> --limit 100
```

MCP exposes the same reads as `operon_plan_events`, `operon_plan_attempts`,
`operon_plan_logs` and `operon_plan_artifacts`. Bounds, ownership and execution
permissions are enforced by the same API/service/pool chain.

## Verification and remaining acceptance

The focused grouped check used the project's validated Python environment with
automatic pytest plugins disabled. It completed with **53 passed, 3 skipped**
in `verification/backend/results-u.log` and `results-u.xml`:

```text
python -m pytest tests/test_plan_results.py tests/test_plan_service.py tests/test_engine_state.py
```

The three skips are actual Windows refusal to create fixture symlinks/ancestor
links (`WinError 1314`) or a hardlink (`WinError 5`). A focused repeat using
extended Windows paths still skipped those three cases; evidence is in
`verification/backend/results-u-links.log` and `results-u-links.xml`. These
skips do not establish runtime link-confinement coverage on this host. Normal
and legacy-layout log reads, byte continuation and the final Windows handle
check did pass. One existing Starlette/httpx deprecation warning was reported.
Static AST syntax checks also passed before the source freeze.

Retain relevant headless, pool, invocation, CLI/MCP permission and authoring-v2
regressions. Cases authored here cover compile-without-submit, strict bindings,
stale plan identity, missing bindings/pool, no retry after uncertain submit,
session/principal forwarding and API/CLI/MCP permission/delegation. Synthetic
pool adapters validate routing and authorization only; they do not prove actual
scientific execution, environment preparation, output parity, Linux, Slurm or
multi-host behavior.

The current HTTP result includes compact status, bounded logs and paged durable
metadata. It is not yet a portable artifact preview/download API or the full K11
human/agent workflow. New result tests exercise real SQLite ownership, event
retention, byte/page limits, committed/reused artifact filtering, log confinement
and API/CLI/MCP delegation. They do not prove real scientific execution or
artifact viewer compatibility; those acceptance gates remain separate.
Storage-to-storage transfers and the existing K07 real-transport gates remain
separate limitations recorded in `backend_k07.md`.

The Settings/Servers storage browser is now wired to authorized root discovery,
bounded directory pages and previews through the shared storage API. This is
partial UI integration: it returns StorageRefs and does not yet resolve them
into legacy graph DataSources or execution bindings. Existing compute profiles
and workflow file selection remain unchanged. Component-test evidence and the
remaining transport/execution boundaries are recorded in `backend_k07.md`; this
does not establish a frontend RunPlan editor or complete K11 execution wiring.

The explicit asynchronous RunPlan export facade is documented separately in
`backend_k11_plan_exports.md`. `backend_cli_quickstart.md` combines the plan,
offline environment, export and storage commands with their remaining gates.
