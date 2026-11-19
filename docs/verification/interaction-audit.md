# Interactive control audit (5.7.x)

This page records the control-by-control audit required by the 5.7 release
series: every interactive control must have a frontend call, a backend
implementation, a real state or log in the response, and a readable failure
reason, and the local and remote execution paths must both work.

Status values:

- `verified` - exercised against a clean installation of the shipped build.
- `covered` - implementation and endpoint verified through automated tests and
  a local API probe, but not clicked through the packaged UI in this cycle.
- `platform` - blocked by an operating-system limitation, with a readable
  reason shown in the UI.

## Runtime status panel

| Control | Frontend call | Backend | Local | Remote | Status |
| --- | --- | --- | --- | --- | --- |
| Execution target selector | `onTarget` -> `remoteEnvironments` | `GET /api/remote/{key}/environments` | n/a | `operon.remote.server.environment_snapshot` | verified (5806/5811) |
| Refresh | `onRefresh` | `GET /api/environments` | `src/web/environment_api.py` | remote snapshot | verified |
| Install all | `onPrepareAll` | `POST /api/environments/prepare` | serial queue, sorted by expected size | `environments_prepare` | verified (5803, 5806) |
| Environment card / expand | `setDetail` | `GET /api/environments` | same payload | same payload | verified |
| Prepare / repair | `onAction('prepare')` | `POST /api/environments/prepare` | `environment_install.prepare` | `environments_prepare` | verified |
| Cancel (running or queued) | `onCancel` | `POST /api/environments/{name}/cancel` | `cancel()` -> `signal_stop` + `mark_cancelled` | `environment_cancel` | verified (200 with `completed`/`reason`) |
| View log | `loadLog` | `GET /api/environments/{name}/log` | tail of `.operon-environment-*.log` | `environment_log` | verified (fixed overlay drawer) |
| Dependency card | `setView('deps')` | `GET /api/environments` (`dependencies`) | `environment_api.dependencies` | same payload | verified |
| Install dependency | `runDependency` | `POST /api/environments/{name}/dependencies/download` | `install_dependency` | `environment_dependency` | verified (202, job) |
| Install all dependencies | `act('prepare')` | `POST /api/environments/{name}/dependencies/download` | same | same | covered |
| Resource card | `setView('resources')` | `GET /api/resources` | `resource_api.snapshot` | remote `resources` | verified |
| Link directory | `onLink` -> `POST /api/v1/large-resources/{name}/link` | `resource_link.link` | local junction/symlink | `resources_link` | verified (junction round trip) |
| Unlink | `onUnlink` -> `DELETE .../link?unit=` | `resource_link.unlink` | local | `resources_unlink` | verified |
| Download unit | `onDownload` -> `POST /api/resources/{name}/download` | `resource_api.start` | local stream, mirror fallback | `resources_download` (5.6.4+) | verified (only missing files) |
| Browse directory (picker) | `POST /api/browse` | `src/web/api.py` `browse` | drive/dir/file list | `remote/browse` | verified |
| Back | `setView('root')` | n/a | n/a | n/a | verified |
| Shared pool stop / force clear | `stopPool` | `POST /api/pool/stop` | `pool_service` | `pool_stop` | covered |

## Resource settings section

| Control | Frontend call | Backend | Status |
| --- | --- | --- | --- |
| Refresh resources | `load` | `GET /api/resources` | verified |
| Download all missing | `downloadAll` | `POST /api/resources/{name}/download` per unit | verified |
| Link dialog submit | `submitLink` | `POST /api/v1/large-resources/{name}/link` | verified |
| Browse (link dialog) | `loadPicker` | `POST /api/browse` | verified |
| Picker parent / drive / entry | `loadPicker` | `POST /api/browse` | verified |
| Cancel dialogs | local state | n/a | verified |

## Deliberate platform behaviour

`antismash`, `genomics`, `hic`, `hmmer` and `rna` declare
`platforms: ["linux", "darwin"]`. On Windows the panel disables Prepare and
shows "当前系统不支持" with the full reason; `POST /api/environments/prepare`
rejects them in about one second and writes the same reason into the
environment error record. This is intentional, not a missing implementation.

## Known gaps carried forward

- The remote shared-pool stop path is implemented but only covered by automated
  tests, not clicked through the packaged UI.
- `operon environment status <name>` still resolves `<name>` as a workflow
  directory; the environment status is available through `operon environment
  list` today.

## MCP and CLI parity

The desktop panel is not the only surface: the same operations must be reachable
from MCP and from the CLI.

| Operation | MCP tool | CLI | HTTP | Notes |
| --- | --- | --- | --- | --- |
| List environments | `operon_environments` | `operon environment list` | `GET /api/environments` | remote via `profile_id` |
| Prepare | `operon_environments_prepare` | `operon environment install` | `POST /api/environments/prepare` | serial queue |
| Cancel | `operon_environments_cancel` | `operon environment cancel` | `POST /api/environments/{name}/cancel` | returns `completed`/`reason` |
| Environment log | `operon_environment_log` | - | `GET /api/environments/{name}/log` | added in this cycle |
| Install dependency | `operon_environment_dependency_install` | - | `POST /api/environments/{name}/dependencies/download` | kind + requirement |
| List resources | `operon_resources` | `operon resources list` | `GET /api/resources` | |
| Link unit | `operon_resource_link` | - | `POST /api/v1/large-resources/{name}/link` | `unit` optional |
| Unlink unit | `operon_resource_unlink` | - | `DELETE /api/v1/large-resources/{name}/link?unit=` | |
| Download unit | `operon_resource_download` | - | `POST /api/resources/{name}/download` | `unit` + `profile_id` |
| Resource log | `operon_resource_log` | - | `GET /api/v1/large-resources/{name}/log` | |

Measured on the 5.7.7 build: 78 MCP tools; `operon_resources`,
`operon_resource_link`, `operon_resource_unlink`, `operon_resource_download`,
`operon_environment_dependency_install` and `operon_browse` declare
`profile_id`, so local and remote take the same path. `operon environment list`,
`operon resources list` and `operon library list` return the same records the
panel shows.

`operon_environment_log` was added during this cycle; its registration was
confirmed through `tools/list`, and its runtime call is verified again with the
next packaged build because a running instance keeps the tool table it started
with.

## 5.7.8 additions

| Control | Frontend call | Backend implementation | Local | Remote | State |
| --- | --- | --- | --- | --- | --- |
| Dependency card install button | `POST /api/environments/{name}/dependencies/download` | `start_dependency` queues a tracked job, appends the command output to the environment log | verified | verified (agent queues a worker and answers with `queued`) | covered |
| Dependency card install on an unprepared environment | same endpoint | rejects with 409 and `环境 <name> 还没有准备好…` without touching the disk | verified | verified | covered |
| Environment card resource gap chip | `GET /api/resources` (remote: `GET /api/remote/{key}/resources`) | `resource_api.snapshot` states per resource | verified | verified | covered |
| CLI `operon environment dependency` | HTTP from `operon/cli.py` | same endpoint, `--profile` routes to `/remote/{id}` | verified | covered | covered |
| CLI `operon environment log` | `GET /v1/environments/{name}/log` | environment log file tail | verified | covered | covered |
| MCP `operon_environment_log` | tool handler | same endpoint, `profile_id` selects the remote | verified | covered | covered |

A dependency install never runs inline in an HTTP request any more: it enters the same
serial queue as environment preparation, writes `.operon-environment-progress/<name>.json`
and its log, and reports through the operation list. Installer steps are supervised by a
60 second silence watchdog so a stalled download fails with a readable message instead of
sitting in `installing` for up to 40 minutes.

### CLI parity fixes (5.7.8)

| Control | CLI command | Backend | Notes |
| --- | --- | --- | --- |
| Environment log | `operon environment log <name> --limit N` | `GET /api/v1/environments/<name>/log` | Fixed two defects: the name was swallowed by the positional `file` argument, and the request used POST (payload `{}`) against a GET-only route, which returned `405 Method Not Allowed`. |
| Dependency install | `operon environment dependency <name> <kind> <requirement> [--profile id]` | `POST /api/v1/environments/<name>/dependencies/download` | Queues a job and returns immediately; a missing environment answers 409 with a readable reason. |
| Resource log | `operon resources log <name>` | `GET /api/v1/large-resources/<name>/log` | Already GET; verified against the installed build. |

## 5.7.9 additions

| Control | Front end | Back end | Local | Remote |
| --- | --- | --- | --- | --- |
| environment readiness chip (six states) | RuntimeStatusPanel readinessOf | /api/environments interpreter+error+dependency_total/installed | yes | yes (remote snapshot carries the same fields) |
| log drawer | loadLog -> api.environmentLog / remoteEnvironmentLog | GET /api/environments/{name}/log, GET /api/remote/{key}/environments/{name}/log | yes | yes |
| persisted environment log file | n/a | .operon-environment-logs/<name>.log written by prepare and dependency installs | yes | yes |
| repair button | runRepair | local POST /api/environments/{name}/retry, remote POST /api/remote/{key}/environments/{name}/retry | yes | yes |
| retry via MCP | n/a | operon_environment_retry(name, profile_id) | yes | yes |
| retry via CLI | n/a | operon environment retry <name> | yes | yes (--profile) |
| environment status via CLI | n/a | operon environment status <name> | yes | yes (--profile) |

## MCP and CLI parity (audited 2026-11-20)

Rule: a control that reads or mutates data must reach the shared service over HTTP and
must be exposed by both the MCP adapter and the CLI. Method: enumerated the 107
`@server.tool()` functions in `operon/mcp_server.py`, the 32 CLI commands in
`operon/cli.py`, 242 route decorators in `src/web/*.py`, `operon/*_api.py` and
`operon/bridge.py`, and every member of the `api` object in `frontend/src/api.ts`.
Theme, panel width and other cosmetic state were excluded.

`operon/client.py` rewrites adapter paths: `'/v1/...'` becomes `/api/v1/...` and any
other path becomes `/api/agent/...`. An adapter can therefore only reach `/api/v1/*`
or `/api/agent/*`, so a browser-only route needs an agent twin before a wrapper can
exist; that rule produced most of the gaps below.

### Closed in this pass

| UI control | HTTP route | MCP tool | CLI verb |
| --- | --- | --- | --- |
| capabilities / status panel | `GET /api/v1/capabilities` | `operon_capabilities` | `operon capabilities` |
| service status, stop service | `GET /api/v1/service`, `POST /api/v1/service/stop` | `operon_service_status`, `operon_service_stop` | `operon service status\|stop` |
| engine badge, event drawer | `GET /api/v1/engine`, `GET /api/v1/engine/events` | `operon_engine_status`, `operon_engine_events` | `operon engine status\|events` |
| environment summary | `GET /api/v1/environment` | `operon_environment_status` | `operon environment status` |
| execution settings of a job | `GET /api/v1/jobs/{id}/parameters` | `operon_job_parameters` | `operon jobs parameters` |
| resource limits | `GET /api/v1/resources` | `operon_resource_limits` | `operon resources limits` |
| viewer settings | `GET /api/v1/viewers`, `POST /api/v1/viewers/default`, `POST /api/v1/viewers/{id}/configure` | `operon_viewers`, `operon_viewer_default`, `operon_viewer_configure` | `operon viewers list\|configure\|default` |
| prepare viewer | `POST /api/v1/jobs/{j}/artifacts/{a}/prepare-viewer` | `operon_viewer_prepare` | `operon artifacts prepare-viewer` |
| storage picker | `GET /api/v1/storage/roots`, `POST /api/v1/storage/{stat,browse,preview}`, `POST /api/v1/storage/browse/close`, `GET /api/v1/storage/status` | `operon_storage_roots`, `_stat`, `_browse`, `_preview`, `_close`, `_status` | `operon storage roots\|stat\|browse\|preview\|close\|status` |
| directory picker (local + remote) | `POST /api/agent/browse`, `POST /api/agent/remote/{key}/browse` | `operon_browse` | `operon browse --path` |
| remote profile save/connect/trust | `POST /api/v1/remotes`, `/api/v1/remotes/{key}/connect`, `/api/v1/remotes/{key}/trust` | `operon_remote_save`, `operon_remote_connect`, `operon_remote_trust` | `operon servers save\|connect\|trust` |
| remote install, setup status | `POST /api/agent/remote/{key}/install`, `GET /api/agent/remote/{key}/setup` | `operon_remote_install`, `operon_remote_install_status` | `operon servers install\|setup` |
| remote library plan/status/sync | `GET /api/agent/remote/{key}/library/{plan,status}`, `POST /api/agent/remote/{key}/library/sync` | `operon_remote_library_plan`, `_status`, `_sync` | not exposed (see gaps) |
| remote environment retry/cancel/dependency | `POST /api/agent/remote/{key}/environments/{name}/{retry,cancel,dependencies/download}` | `operon_environment_retry`, `operon_environments_cancel`, `operon_environment_dependency_install` | `operon environment retry\|cancel\|dependency --profile` |
| remote resource download | `POST /api/agent/remote/{key}/resources/{name}/download` | `operon_resource_download` (`profile_id`) | `operon resources download --profile` |
| plugin list | `GET /api/agent/plugins` | `operon_plugins` | `operon plugin list` (reads the library from disk, not HTTP) |
| canvas plan prepare/execute/cancel/status/history/outcome | `POST /api/v1/canvas-plans/{prepare,execute,cancel}`, `GET /api/v1/canvas-plans/{status,history,outcome}` | `operon_canvas_prepare`, `_execute`, `_cancel`, `_status`, `_history`, `_outcome` | `operon canvas prepare\|execute\|cancel\|status\|history\|outcome` |

Scope decisions follow the HTTP routes they mirror: `canvas prepare\|cancel\|execute`,
`servers install` and `resources download` ask for `run`, environment install, retry,
cancel and dependency install ask for `plugins`, and everything read-only uses
`context` (`edit` remains the default for the rest).

### Adapter defects fixed

- `operon_browse` and no CLI verb: the tool targeted `/api/agent/browse`, which did not
  exist (404), and sent `show_files` while the shared helper reads `files`. Added both
  agent browse routes, a `browse` CLI command, and a payload that carries both keys.
- `operon_remote_library_plan/status/sync`: pointed at
  `/api/agent/remote/{key}/library/*`, which had no routes. Added the three routes.
- remote environment retry, cancel and dependency install: the `/api/remote/...` forms
  exist but had no agent twin, so `--profile` variants of those CLI verbs and the
  `profile_id` argument of the MCP tools returned 404. Added three agent routes.
- remote resource download: same defect, `profile_id` variants 404. Added the route.
- `operon environment dependency` (local): the environment name was captured by the
  positional `file` argument, the same defect 5.7.8 fixed for `environment log`, so
  `operon environment dependency web pip numpy` installed into `pip`. Fixed.

### Gaps that remain

| Control | HTTP route | Why it is not a thin wrapper |
| --- | --- | --- |
| language, theme | `GET/POST /api/preferences` | desktop profile file with no `/v1` twin; headless preference storage needs a product decision |
| plugin refresh/enable/disable/remove/declarations/open-folder/dependencies | `/api/plugins/*` | the agent gateway exposes list and install only; the rest mutate the installed library or open OS windows |
| route collections list/delete | `GET /api/route-collections`, `DELETE /api/route-collections/{slug}` | only import has a `/v1` twin |
| library state / manage | `GET /api/library/state`, `POST /api/library/manage` | desktop library enable/disable/restore |
| workflow import (zip), route archive import | `/api/workflows/import`, `/api/routes/import-archive` | multipart zip uploads; agents import by path over `/v1` instead |
| workflow export (yaml, zip) | `/api/workflows/export`, `/api/workflows/export-yaml` | CLI has `workflow export`; the MCP tool is still missing |
| script inspect/extract/publish | `/api/scripts/*` | canvas authoring, no agent route |
| asset upload and batches | `/api/assets*` | browser streaming uploads; agents write through `/v1/workspace/files` |
| execution pre-flight | `/api/execution/plan`, `/api/execution/resources` | desktop-only preview; `/v1/resources` covers the limits half |
| workspace read | `GET /api/workspace` | agents can write but not read the workspace tree |
| contracts, bundle export/import | `/api/contracts`, `/api/export`, `/api/import` | desktop YAML bundle exchange |
| remote refresh/build/source/disconnect/remove, library check/install | `/api/remote/{key}/*` | not exposed on the agent gateway |
| remote resource cancel/log | none | the remote agent protocol only implements resources list/link/unlink/download, so `operon resources cancel\|log --profile` cannot be a wrapper |
| remote library via CLI | `GET/POST /api/agent/remote/{key}/library/*` | routes exist for MCP; a `servers library plan\|status\|sync` verb is not added yet |

`tests/test_parity_control_plane.py` pins these forwards: one parametrised case per MCP
tool and per CLI verb asserts the exact `(path, payload)` pair reaching the client, and
a source guard keeps the agent routes that the adapters depend on. The focused suite
(`test_parity_control_plane`, `test_server_cli`, `test_pool_cli`, `test_result_viewers`,
`test_mcp_installation_guard`, `test_operon_branding`, `test_agent_transports`) reports
98 passed.
