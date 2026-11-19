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
