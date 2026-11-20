# Frontend API, MCP tool and CLI parity

## Scope

`frontend/src/api.ts` is the desktop HTTP surface: one exported `api` object whose methods are
thin wrappers over `request()`/`requestFile()` (plus raw `fetch` for binary uploads).
`operon/mcp_server.py` is the agent surface served over MCP stdio, and `operon/cli.py` is the
terminal surface. The product requirement is that every method of the frontend API has a
corresponding MCP tool, that methods which deliberately have none are justified, that MCP
writes are subject to the same token and scope checks as the HTTP route, and that remote
operations carry a `profile_id` and travel the same authorization channel as every other call.

This document records that audit: the method-by-method mapping, the deliberate omissions with
their reasons, the known limitations, and the gaps that were closed. `tests/test_mcp_parity.py`
enforces the mapping and pins the method count at 106, so a frontend method cannot be added
without either a tool or a reasoned allowlist entry.

## Three route families

| Family | Prefix | Reached by | Authentication |
| --- | --- | --- | --- |
| Studio surface | `/api/...` | browser `request()` | `X-Studio-Token` (CSRF device for the SPA) |
| Agent bridge | `/api/agent/...` | `Client.request()` for literals without a `/v1` prefix | bridge token from `/api/agent/connect`, per-scope |
| Control plane | `/api/v1/...` | `Client.request('/v1/...')` | bearer token, `authorize(request, scope)` |

`operon/client.py` chooses the family from the literal: a path starting with `/v1/` becomes
`/api/v1/<path>`, anything else becomes `/api/agent/<path>`. `operon/bridge.py` mirrors the UI
routes one by one and has no catch-all, so a method is agent-reachable only when a bridge or
`/v1` route exists. Both families authenticate with a token and enforce the same scopes as the
HTTP surface (`authorize(request, 'edit' | 'plugins' | ...)`); the studio token is never needed
by an agent. A `403` triggers one transparent re-connect, except for the two environment
preparation paths, where a denied `plugins` scope must not silently turn into an install.

Remote operations: every tool that addresses one server takes `profile_id` and posts through
the bridge (or the `/v1/remotes/...` twin). The two profile-collection tools,
`operon_remote_status` and `operon_remote_save`, have no single addressee and therefore no
`profile_id`; `tests/test_mcp_parity.py` pins that exception.

## Coverage

- 106 methods in `frontend/src/api.ts`.
- 98 map to an MCP tool (one is degraded, see below).
- 8 are deliberately not mapped: six browser/transport chores and two desktop/async-UI chores.

| API method | HTTP verb | HTTP path | MCP tool | CLI |
| --- | --- | --- | --- | --- |
| `catalogIfChanged` | GET | `/api/operators` | `operon_catalog` | operators list |
| `inspectScript` | POST | `/api/scripts/inspect` | `operon_script_inspect` | script inspect |
| `extractScript` | POST | `/api/scripts/extract` | `operon_script_extract` | script extract |
| `publishScript` | POST | `/api/scripts/publish` | `operon_script_publish` | script package |
| `operatorSource` | GET | `/api/operators/{id}/source` | `operon_operator_source` | - |
| `prepareEnvironment` | POST | `/api/prepare-environment` | `operon_workflow_prepare_environment` | workflow prepare-environment |
| `checkEnvironment` | POST | `/api/check-environment` | `operon_workflow_check_environment` | environment check |
| `environments` | GET | `/api/environments` | `operon_environments` | environment list |
| `prepareEnvironments` | POST | `/api/environments/prepare` | `operon_environments_prepare` | environment prepare |
| `remoteEnvironmentRetry` | POST | `/api/remote/{key}/environments/{name}/retry` | `operon_environment_retry` | environment retry --profile |
| `retryEnvironment` | POST | `/api/environments/{name}/retry` | `operon_environment_retry` | environment retry |
| `environmentLog` | GET | `/api/environments/{name}/log` | `operon_environment_log` | environment log |
| `cancelEnvironment` | POST | `/api/environments/{name}/cancel` | `operon_environments_cancel` | environment cancel |
| `version` | GET | `/api/version` | `operon_version` | - |
| `pool` | GET | `/api/pool` | `operon_pool_status` | pool status |
| `stopPool` | POST | `/api/pool/stop` | `operon_pool_stop` | pool stop |
| `remotePoolStop` | POST | `/api/remote/{id}/pool/stop` | `operon_remote_pool_stop` | - |
| `remoteEnvironments` | GET | `/api/remote/{id}/environments` | `operon_environments` | environment list --profile |
| `remotePrepareEnvironments` | POST | `/api/remote/{id}/environments/prepare` | `operon_environments_prepare` | environment prepare --profile |
| `remoteEnvironmentDependencyDownload` | POST | `/api/remote/{id}/environments/{name}/dependencies/download` | `operon_environment_dependency_install` | environment dependency --profile |
| `remoteCancelEnvironment` | POST | `/api/remote/{id}/environments/{name}/cancel` | `operon_environments_cancel` | environment cancel --profile |
| `remoteEnvironmentLog` | GET | `/api/remote/{id}/environments/{name}/log` | `operon_environment_log` | environment log --profile |
| `remoteResources` | GET | `/api/remote/{id}/resources` | `operon_resources` | resources list --profile |
| `remoteLinkResource` | POST | `/api/remote/{id}/resources/{name}/link` | `operon_resource_link` | resources link --profile |
| `remoteUnlinkResource` | DELETE | `/api/remote/{id}/resources/{name}/link` | `operon_resource_unlink` | resources unlink --profile |
| `savePreferences` | POST | `/api/preferences` | `operon_preferences_save` | - |
| `viewers` | GET | `/api/v1/viewers` | `operon_viewers` | viewers list |
| `configureViewer` | POST | `/api/v1/viewers/{id}/configure` | `operon_viewer_configure` | viewers configure |
| `defaultViewer` | POST | `/api/v1/viewers/default` | `operon_viewer_default` | viewers default |
| `artifactViewers` | GET | `/api/v1/jobs/{job}/artifacts/{artifact}/viewers` | `operon_viewer` | artifacts viewers |
| `openViewer` | POST | `/api/v1/jobs/{job}/artifacts/{artifact}/open-viewer` | `operon_viewer` | artifacts open |
| `prepareViewer` | POST | `/api/v1/jobs/{job}/artifacts/{artifact}/prepare-viewer` | `operon_viewer_prepare` | artifacts prepare-viewer |
| `executionPlan` | POST | `/api/execution/plan` | `operon_execution_plan` | - |
| `executionResources` | GET | `/api/execution/resources` | `operon_execution_resources` | - |
| `remoteStatus` | GET | `/api/remote` | `operon_remote_status` | servers list |
| `saveRemote` | POST | `/api/remote/profiles` | `operon_remote_save` | servers save |
| `connectRemote` | POST | `/api/remote/{id}/connect` | `operon_remote_connect` | servers connect |
| `installRemote` | POST | `/api/remote/{id}/install` | `operon_remote_install` | servers install |
| `refreshRemote` | POST | `/api/remote/{id}/refresh` | `operon_remote_refresh` | - |
| `checkRemoteLibrary` | POST | `/api/remote/{id}/library/check` | `operon_remote_library_check` | - |
| `installRemoteLibrary` | POST | `/api/remote/{id}/library/install` | `operon_remote_library_install` | - |
| `remoteLibraryStatus` | GET | `/api/remote/{id}/library/status` | `operon_remote_library_status` | - |
| `remoteLibraryPlan` | GET | `/api/remote/{id}/library/plan` | `operon_remote_library_plan` | - |
| `syncRemoteLibrary` | POST | `/api/remote/{id}/library/sync` | `operon_remote_library_sync` | - |
| `remoteSetup` | GET | `/api/remote/{id}/setup` | `operon_remote_install_status` | servers setup |
| `trustRemote` | POST | `/api/remote/{id}/trust` | `operon_remote_trust` | servers trust |
| `disconnectRemote` | POST | `/api/remote/{id}/disconnect` | `operon_remote_disconnect` | - |
| `removeRemote` | POST | `/api/remote/{id}/remove` | `operon_remote_remove` | - |
| `browsePath` | POST | `/api/browse` | `operon_browse` | browse |
| `browseRemote` | POST | `/api/remote/{id}/browse` | `operon_browse` | - |
| `sourceRemote` | POST | `/api/remote/{id}/source` | `operon_remote_source` | - |
| `largeResources` | GET | `/api/resources` | `operon_resources` | resources list |
| `largeResourceLink` | POST | `/api/resources/{name}/link` | `operon_resource_link` | resources link |
| `largeResourceUnlink` | DELETE | `/api/resources/{name}/link` | `operon_resource_unlink` | resources unlink |
| `largeResourceDownload` | POST | `/api/resources/{name}/download` | `operon_resource_download` | resources download |
| `remoteResourceDownload` | POST | `/api/remote/{id}/resources/{name}/download` | `operon_resource_download` | resources download --profile |
| `environmentDependencyDownload` | POST | `/api/environments/{name}/dependencies/download` | `operon_environment_dependency_install` | environment dependency |
| `storageRoots` | GET | `/api/v1/storage/roots` | `operon_storage_roots` | storage roots |
| `browseStorage` | POST | `/api/v1/storage/browse` | `operon_storage_browse` | storage browse |
| `statStorage` | POST | `/api/v1/storage/stat` | `operon_storage_stat` | storage stat |
| `previewStorage` | POST | `/api/v1/storage/preview` | `operon_storage_preview` | storage preview |
| `closeStorageBrowse` | POST | `/api/v1/storage/browse/close` | `operon_storage_close` | storage close |
| `plugins` | GET | `/api/plugins` | `operon_plugins` | plugin list |
| `refreshPlugins` | POST | `/api/plugins/refresh` | `operon_plugins_refresh` | plugin refresh |
| `repairDependencies` | POST | `/api/plugins/dependencies` | `operon_plugins_dependencies` | - |
| `openPluginFolder` | POST | `/api/plugins/open-folder` | - | - |
| `pluginOperation` | GET | `/api/plugins/operations/{id}` | - | - |
| `removePlugin` | POST | `/api/plugins/remove` | `operon_plugins_remove` | plugin remove |
| `managePlugin` | POST | `/api/plugins/manage` | `operon_plugins_manage` | plugin enable / disable |
| `installPlugin` | POST | `/api/plugins/install` | `operon_plugin_install` | plugin install |
| `libraries` | GET | `/api/libraries` | `operon_library_list` | library list |
| `installLibrary` | POST | `/api/libraries/install` | `operon_library_install` | library install |
| `deleteLibrary` | DELETE | `/api/libraries/{name}` | `operon_library_remove` | library remove |
| `routeCollections` | GET | `/api/route-collections` | `operon_route_collections` | - |
| `deleteRouteCollection` | DELETE | `/api/route-collections/{slug}` | `operon_route_collection_remove` | - |
| `agent` | POST | `/api/agent{path}` | - | - |
| `catalog` | GET | `/api/operators` | `operon_catalog` | operators list |
| `workspace` | GET | `/api/workspace` | `operon_workspace` | - |
| `saveWorkspace` | POST | `/api/workspace` | `operon_workspace_save` | - |
| `workflows` | GET | `/api/workflows` | `operon_workflows` | workflow list |
| `workflow` | GET | `/api/workflows/{id}` | `operon_workflows` | workflow get |
| `prepareWorkflow` | POST | `/api/workflows/prepare` | `operon_workflow_prepare` | workflow prepare |
| `exportWorkflow` | POST | `/api/workflows/export-yaml` | `operon_workflow_export` | workflow export |
| `importWorkflow` | POST | `/api/workflows/import` | `operon_workflow_import` | - |
| `saveWorkflow` | POST | `/api/workflows/save` | `operon_workflow_save` | workflow save |
| `importRouteArchive` | POST | `/api/routes/import-archive` | `operon_routes_import_archive` | - |
| `importRouteCollection` | POST | `/api/routes/import-collection` | `operon_routes_import` | routes import |
| `routes` | GET | `/api/routes` | `operon_routes` | - |
| `libraryState` | GET | `/api/library/state` | `operon_library_state` | - |
| `manageLibrary` | POST | `/api/library/manage` | `operon_library_manage` | - |
| `registerRoutes` | POST | `/api/routes/register` | `operon_routes_register` | - |
| `bootstrap` | GET | `/api/bootstrap` | - | - |
| `validate` | POST | `/api/validate` | `operon_validate` | graph validate |
| `contracts` | POST | `/api/contracts` | `operon_contracts` | - |
| `export` | POST | `/api/export` | `operon_graph_export` | - |
| `import` | POST | `/api/import` | `operon_graph_import` | - |
| `run` | POST | `/api/jobs` | `operon_submit` | run |
| `history` | GET | `/api/jobs` | `operon_jobs` | jobs list |
| `job` | GET | `/api/jobs/{id}` | `operon_job` | jobs get |
| `cancel` | POST | `/api/jobs/{id}/cancel` | `operon_cancel` | jobs cancel |
| `preview` | GET | `/api/jobs/{id}/artifacts/{artifact}/preview` | `operon_artifacts` | artifacts preview |
| `step` | GET | `/api/jobs/{id}/exports/{index}` | `operon_job_export` | artifacts get |
| `url` | GET | `(none: base + path)` | - | - |
| `uploadFiles` | POST | `/api/assets/batches` | - | - |
| `uploadReference` | POST | `/api/assets/reference` | - | - |
| `upload` | POST | `/api/assets` | - | - |

CLI entries name the closest terminal command; `-` means the terminal surface has no verb for
that method. The CLI is deliberately thinner than MCP: it has no verb for the SPA-only chores
above, for the archive and collection imports and route registration, for workspace, preference
and library-state writes, for remote library management and remote profile refresh/removal, and
for a few read-only control-plane views (execution plan and execution resources, plugin
operation polling, artifact tables). Those are command-line scope decisions, not MCP parity
defects.

## Deliberate omissions

| API method | Why it has no MCP tool | What an agent uses instead |
| --- | --- | --- |
| `agent` | Generic `/api/agent{path}` passthrough. Exposing it would let a caller reach any bridge route and bypass the tool contracts. | The dedicated tools; the MCP transport is itself the bridge channel. |
| `bootstrap` | Hands the SPA a studio token and remembers it in module state. | `operon_status` / `operon_capabilities`; MCP authenticates through `/api/agent/connect`. |
| `url` | Pure `base + path` string join; it performs no HTTP request. | Nothing to call. |
| `upload`, `uploadFiles`, `uploadReference` | Browser `File` choreography: multipart bodies, blob slicing and per-batch accounting. | `operon_task` to open a workspace, then `operon_write_text` / `operon_write_binary`. |
| `openPluginFolder` | Opens the plugin directory in the desktop file manager; there is no HTTP route behind it. | `operon_plugins` reports the directory; an agent cannot observe a GUI side effect. |
| `pluginOperation` | Polls a legacy asynchronous plugin handle. | The bridge and `/v1` plugin routes are synchronous and already return the terminal state. |

## Known limitation

`sourceRemote` (`POST /api/remote/{id}/source`) is mapped to `operon_remote_source`, but the
tool is degraded: the studio route forwards `{path, reader}` so the desktop can import one
chosen file, while the `/api/v1/remotes/{key}/source` route the tool reaches ignores the body
(`operon/control_api.py`), and the bridge has no mirror route. The tool therefore reports
availability only, and its docstring says so.

Remedy, outside the scope of this change: either accept the payload in the `/v1` handler, or
add a bridge mirror `POST /api/agent/remote/{key}/source` that forwards `{path, reader}` like
`src/web/remote_api.py` does. Once either exists, give the tool `path`/`reader` parameters and
drop the limitation note.

## Gaps closed in this change

1. `operon_remote_install` now forwards `password` and `passphrase` to
   `POST /api/agent/remote/{id}/install`. The bridge already read them, but the tool dropped
   them, so a password-protected profile could not be installed from MCP. They are passed for
   that install only and stay in the server's in-memory credential cache (dropped when the
   connection closes), never in the profile file. The write still requires the bridge token and
   the `run` scope the bridge handler checks.
2. `operon_browse` gained `offset` and `hidden` for remote listings. The remote server pages
   200 entries and pages dotfiles behind `hidden`, which the tool could not request.
3. `operon_remote_status` gained `brief=False`, reaching `GET /api/remote` for the full
   per-profile status; the default keeps the compact `GET /api/remote/summary` the desktop list
   uses.
4. `operon_remote_source` documents its limitation in the docstring.
5. `tests/test_mcp_parity.py` was added.

## Keeping it true

- `pytest tests/test_mcp_parity.py -q` checks the mapping, the tool docstrings, the remote
  `profile_id` rule and the allowlist reasons.
- `pytest tests/test_parity_control_plane.py -q` pins the exact route and payload of the tools
  and CLI verbs that go through the shared client.
- Adding a frontend method means adding it to `PARITY` (tool plus the route tokens it must
  call) or to `ALLOWLIST` with a reason; the count in `EXPECTED_API_METHODS` moves with it.
