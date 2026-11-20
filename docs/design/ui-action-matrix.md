# UI action matrix

Static source audit of every interactive control in the Operon Studio frontend, traced from the rendered element to the React handler, the `api.ts` client method, the HTTP route and the FastAPI handler that implements it. The document exists to stop "the button looked fine but nothing happened" bugs: every row names the code that would have to run.

- **Scope.** Frontend: `frontend/src/**/*.tsx` and `frontend/src/*.ts`, i.e. every element carrying `onClick`, `onChange`, `onSubmit`, `onContextMenu`, or a form control whose value is submitted by one of those handlers. Backend: every module that registers a route for a path the frontend calls — `src/web/api.py`, `src/web/environment_api.py`, `src/web/resource_api.py`, `src/web/remote_api.py`, `src/web/remote_service.py`, `src/web/pool_api.py`, `src/web/plugin_api.py`, `src/web/library_api.py`, `src/web/script_api.py`, `src/web/execution_api.py`, `src/web/preferences.py`, `operon/control_api.py`, `operon/bridge.py`, `operon/canvas_api.py`, `operon/plan_api.py`, `operon/plan_ui_state.py`, `operon/plan_binding_options.py`, `operon/viewer_api.py`, `operon/storage_api.py`.
- **Method.** Static reading only. Each frontend row cites the exact `file:line` of the element as read in the source; each handler cites the function that runs it. Each `Client call` cites the method and line in `frontend/src/api.ts` (or `frontend/src/planApi.ts` / a raw `request()` call). Each `HTTP` cell cites the backend decorator line that registers that method+path. Route existence was checked by matching a 294-decorator inventory of `src/web/*.py` and `operon/*.py` (`grep -rn --include=*.py -E '@(app|router)\.(get|post|put|delete|patch)' src/web operon`) against each frontend path.
- **Nothing was executed.** No control in this document was clicked, no request was sent, no server was started. "Verified" therefore means *statically confirmed to exist and be reachable in code*, not *observed working at runtime*.
- **Rows that could not be fully confirmed statically** are marked `unclear` in the `Status` column and are itemised in [Gaps](#gaps).
- **Generated:** 2026-11-20 (Asia/Shanghai). **Repository commit:** `f186371c5`. The audit was taken against the working tree, which also carried uncommitted edits to `operon/environment_install.py`, `operon/remote/server.py`, `src/web/api.py`, `src/web/environment_api.py`, `src/web/resource_api.py` and several test modules; findings that depend on those files describe the working-tree state rather than the commit alone.

## How to read this table

| Column | Meaning |
| --- | --- |
| `#` | Row number, stable for cross-referencing from `Backend endpoints` and `Gaps`. |
| `Surface` | The panel or window the control is rendered in, e.g. `Runtime status`, `Large resources`, `Settings → Servers`, `Runs`, `Canvas toolbar`. |
| `Control` | The visible label exactly as authored in the source (Chinese labels are preserved verbatim); the element kind is noted in parentheses. Icon-only buttons use their `aria-label`. |
| `Source` | `path:line` relative to the repository root. A line range means the element spans or is generated on those lines. |
| `Handler` | The React callback invoked, plus its definition line when it is a named function in the same file. `onClick={() => …}` denotes an inline arrow. |
| `Client call` | The method on the `api` object in `frontend/src/api.ts` (line cited), or `planApi.*` in `frontend/src/planApi.ts`, or a raw `request()`/`<a href>` that bypasses the `api` object. |
| `HTTP` | HTTP method and path template as the client builds it, plus the backend decorator `file:line` that registers it. `{key}`, `{name}` etc. are the client-side interpolations. |
| `Server handler` | The backend function that implements the route (`file:line` of the `def`/`async def`). |
| `Effect` | The observable side effect: enqueues a job, writes a progress/log file, mutates a manifest, reads a snapshot, or changes frontend state only. |
| `States` | UI state the control depends on or drives, using the vocabulary the code uses (`queued → installing → ready`, `preparing → ready`, `busy`, dialog open/closed). |
| `Error paths` | Non-2xx responses the backend can produce and how the frontend surfaces them. `none observed in code` means no failure branch exists on either side. |
| `Status` | `verified` — route and handler both exist and the mapping is unambiguous. `degraded` — the route exists but resolves to the wrong or partial behaviour. `route missing` — the frontend calls a path with no matching backend registration (all such rows are re-listed in `Gaps`). `frontend-only` — no HTTP call at all. `unclear` — could not be confirmed statically. |

Two structural notes that explain many of the `HTTP` cells:

1. `/api/...` and `/api/v1/...` are served by **one** FastAPI app. `src/web/api.py:53` creates it; `:59-80` mounts the studio modules and `mount_control`; `operon/control_api.py:109` mounts `mount_viewers`, `mount_storage`, `mount_plans`; `operon/plan_api.py:25` mounts `mount_canvas`, `mount_binding_options`, `mount_plan_ui_state`. There is no separate port or process for the v1 surface.
2. Auth is a middleware, not a dependency. `src/web/api.py:90-100` rejects non-local hosts and requires `x-studio-token` on mutating `/api/*` requests **except** `/api/v1/*` and `/api/agent/*`; those two families authenticate per handler through `Bridge.actor()` (`operon/bridge.py:51-65`), which accepts the studio token or a scoped `Authorization: Bearer` agent token. GET routes are not token-gated, which is what makes plain `<a href>` downloads work.

## Controls

| # | Surface | Control | Source | Handler | Client call | HTTP | Server handler | Effect | States | Error paths | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Runtime status | `执行位置` (select, `aria-label`) | `frontend/src/RuntimeStatusPanel.tsx:285` | `onChange` → `onTarget` → `chooseTarget` (`:724-727`) | `api.remoteEnvironments` (`api.ts:178`) | `GET /api/remote/{key}/environments` — `src/web/remote_api.py:82` | `remote_environments` (`src/web/remote_api.py:83-85`) | Reads the selected remote profile's environment snapshot and swaps the panel list from local to remote | panel target `'' → <profile key>`; list refetch every 3 s while set (`:544-561`) | `409`/`422` `RemoteError` with `{message, code, node_id}` (`remote_api.py:16-21`), rendered in the panel error line | verified |
| 2 | Runtime status | `刷新` (button) | `frontend/src/RuntimeStatusPanel.tsx:290` | `onRefresh` (`:797-799`) | `api.environments` (`api.ts:165`) / `api.remoteEnvironments` (`api.ts:178`) | `GET /api/environments` — `src/web/environment_api.py:679`; remote variant as row 1 | `list_environments` (`environment_api.py:680-682`) | Re-reads the snapshot (`snapshot()` at `:417-467`) and re-renders readiness, dependency counters and resource counters | `idle → loading → idle`; keeps `detail`/`log` drawers open | `409` on `ValueError` from the snapshot builder; otherwise the middleware 500 (`api.py:110`) | verified |
| 3 | Runtime status | `全部安装` (button, summary strip) | `frontend/src/RuntimeStatusPanel.tsx:291` | `onPrepareAll` (`:800-802`) | `api.prepareEnvironments` (`api.ts:166`) / `api.remotePrepareEnvironments` (`api.ts:180`) | `POST /api/environments/prepare` — `src/web/environment_api.py:698`; remote `POST /api/remote/{key}/environments/prepare` — `remote_api.py:86` | `prepare` (`environment_api.py:699-726`); `manager.prepare_environments` (`remote_api.py:86`) | Enqueues one install job per environment (returns `prepared: [{name, job, status}]`); remote variant enqueues on the remote host | every env card `queued → installing → ready` (or `incomplete`) | `422` for unknown payload fields (`不认识的字段…`) or non-list `names`; `404` unknown environment; `409`; remote `409`/`422` `RemoteError` | verified |
| 4 | Runtime status | Environment card (whole card, `role="button"`) | `frontend/src/RuntimeStatusPanel.tsx:309` | `onClick` → `onOpen` → `setDetail` (`:823`) | — | — | — | Opens the environment detail modal; no request | `detail: null → env item` | none observed in code | frontend-only |
| 5 | Runtime status | `准备` (per-environment action) | `frontend/src/RuntimeStatusPanel.tsx:368-376` | `onAction` → `act('prepare', name)` (`:653-706`) | `api.prepareEnvironments` (`api.ts:166`) | `POST /api/environments/prepare` — `src/web/environment_api.py:698` | `prepare` (`environment_api.py:699-726`) | Enqueues an install job for one environment | card `ready/incomplete → installing` | `422`/`404`/`409` as row 3 | verified |
| 6 | Runtime status | `修复` (per-environment action) | `frontend/src/RuntimeStatusPanel.tsx:368-376` | `act('repair')` → `api.retryEnvironment` (`:676`) | `api.retryEnvironment` (`api.ts:168`) | `POST /api/environments/{name}/retry` — `src/web/environment_api.py:727` | `retry` (`environment_api.py:727`) | Re-runs installation for a failed/partial environment; returns `{**snapshot(), job}` | `failed/incomplete → installing` | `404` unknown environment (`:727`); `409` when a job is already running | verified |
| 7 | Runtime status | `查看日志` (per-environment action) | `frontend/src/RuntimeStatusPanel.tsx:368-376` | `act('log')` → `loadLog` (`:638-651`) | `api.environmentLog` (`api.ts:169`) | `GET /api/environments/{name}/log?limit=400` — `src/web/environment_api.py:805` | `read_log` (`environment_api.py:806-826`) | Reads the progress log, falling back to `environment_install.log_path`, then to a synthetic log rendered from progress JSON | `log: null → {name, text}`; drawer open | `404` unknown environment; `limit` clamped to 1..2000 | verified |
| 8 | Runtime status | `取消` (per-environment action) | `frontend/src/RuntimeStatusPanel.tsx:368-376` | `act('cancel')` → `api.cancelEnvironment` (`:685`) | `api.cancelEnvironment` (`api.ts:170`) | `POST /api/environments/{name}/cancel` — `src/web/environment_api.py:745` | `cancel` (`environment_api.py:747-803`) | Cancels a queued or running install; when nothing is cancellable it returns `cancelled:false` plus `reason` (`该环境已完成安装，取消无效。` / `没有正在进行的准备任务。`) | `installing → cancelled/ready`; frontend reads `completed`/`cancelled`/`reason` (`:690-696`) | `404` unknown environment; `200` with `cancelled:false` is treated as a normal result | verified |
| 9 | Runtime status | `准备` (remote environment action) | `frontend/src/RuntimeStatusPanel.tsx:368-376` | `act('prepare')` with `target` set → `api.remotePrepareEnvironments` (`:663`) | `api.remotePrepareEnvironments` (`api.ts:180`) | `POST /api/remote/{key}/environments/prepare` — `src/web/remote_api.py:86` | `remote_prepare_environments` (`remote_api.py:86`) | Forwards `names` + `dependencies` to the remote engine, which enqueues there | remote card `queued → installing → ready` | `409`/`422` `RemoteError`; `503`-class failures surface as `RemoteError` too | verified |
| 10 | Runtime status | `修复` (remote environment action) | `frontend/src/RuntimeStatusPanel.tsx:368-376` | `act('repair')` with `target` → `api.remoteEnvironmentRetry` (`:673`) | `api.remoteEnvironmentRetry` (`api.ts:167`) | `POST /api/remote/{key}/environments/{name}/retry` — `src/web/remote_api.py:100` | `remote_environment_retry` (`remote_api.py:101-102`) | Retries installation on the remote host | remote card `failed/incomplete → installing` | `409`/`422` `RemoteError` | verified |
| 11 | Runtime status | `查看日志` (remote environment action) | `frontend/src/RuntimeStatusPanel.tsx:368-376` | `act('log')` → `loadLog` (`:643`) | `api.remoteEnvironmentLog` (`api.ts:189`) | `GET /api/remote/{key}/environments/{name}/log` — `src/web/remote_api.py:99` | **resolves to `remote_environment_retry` (`remote_api.py:101-102`)** | Opening the remote log drawer re-triggers a retry on the remote host; the intended `remote_environment_log` (`remote_api.py:104-105`) has no decorator and is dead code | drawer never fills; the environment silently re-enters `installing` | none — the retry path returns 200 | degraded |
| 12 | Runtime status | `取消` (remote environment action) | `frontend/src/RuntimeStatusPanel.tsx:368-376` | `act('cancel')` with `target` → `api.remoteCancelEnvironment` (`:658`) | `api.remoteCancelEnvironment` (`api.ts:186`) | `POST /api/remote/{key}/environments/{name}/cancel` — `src/web/remote_api.py:95` | `remote_cancel_environment` (`remote_api.py:96`) | Cancels the remote install job | `installing → cancelled` | `409`/`422` `RemoteError` | verified |
| 13 | Runtime status | `取消` (operation list row) | `frontend/src/RuntimeStatusPanel.tsx:397` | `onCancel` → `act('cancel', name)` (`:825`) | `api.cancelEnvironment` (`api.ts:170`) / `api.remoteCancelEnvironment` (`api.ts:186`) | as rows 8 and 12 | as rows 8 and 12 | Cancels the install job represented by that progress-file row | operation row `running → cancelled` | as rows 8 and 12 | verified |
| 14 | Runtime status | `刷新` (log drawer) | `frontend/src/RuntimeStatusPanel.tsx:417` | `onRefresh` → `loadLog(log.name)` (`:898`) | `api.environmentLog` (`api.ts:169`) / `api.remoteEnvironmentLog` (`api.ts:189`) | as row 7; remote variant hits row 11's collision | as row 7 / row 11 | Re-reads the log tail; for a remote environment this again fires a retry | drawer content replaced | as rows 7 and 11 | degraded |
| 15 | Runtime status | `关闭` (log drawer) | `frontend/src/RuntimeStatusPanel.tsx:418` | `onClose` → `setLog(null)` | — | — | — | Closes the drawer only | `log → null` | none observed in code | frontend-only |
| 16 | Runtime status | Environment detail card `环境依赖` | `frontend/src/RuntimeStatusPanel.tsx:830` | `onClick` → `setView('deps')` | — | — | — | Switches the modal pane to the flattened dependency list | `view: 'root' → 'deps'` | none observed in code | frontend-only |
| 17 | Runtime status | Environment detail card `资源` | `frontend/src/RuntimeStatusPanel.tsx:843` | `onClick` → `setView('resources')` | — (renders `<LargeResourceSection target environment compact/>` at `:890`) | — | — | Switches the modal pane to the embedded large-resource section, which then polls `api.largeResources`/`api.remoteResources` (`LargeResourceSection.tsx:156-169`) | `view: 'root' → 'resources'` | — | frontend-only |
| 18 | Runtime status | `全部安装` (detail modal) | `frontend/src/RuntimeStatusPanel.tsx:858` | `act('prepare', detail.name)` | `api.prepareEnvironments` (`api.ts:166`) | `POST /api/environments/prepare` — `src/web/environment_api.py:698` | `prepare` (`environment_api.py:699-726`) | Same enqueue as row 5, for the modal's environment | `ready/incomplete → installing` | `422`/`404`/`409` | verified |
| 19 | Runtime status | `安装` / `重新安装` (per-dependency row) | `frontend/src/RuntimeStatusPanel.tsx:880` | `onClick` → `runDependency(detail.name, entry.kind, entry.name)` (`:882`) → `runDependency` (`:619-636`) | `api.environmentDependencyDownload` (`api.ts:250`) | `POST /api/environments/{name}/dependencies/download` — `src/web/environment_api.py:683` | `download_dependency` (`environment_api.py:683-697`) | Enqueues a single-dependency install job; response `{status, job, name}` | dependency row `missing → installing → installed` | `404` unknown environment; `409` on `ValueError`/`FileNotFoundError`/`RuntimeError` | verified |
| 20 | Runtime status | `安装` / `重新安装` (remote dependency row) | `frontend/src/RuntimeStatusPanel.tsx:880` | `runDependency` (`:625`) | `api.remoteEnvironmentDependencyDownload` (`api.ts:183`) | `POST /api/remote/{key}/environments/{name}/dependencies/download` — `src/web/remote_api.py:91` | `remote_environment_dependency` (`remote_api.py:92`) | Forwards the dependency install to the remote engine | remote dependency `missing → installing` | `409`/`422` `RemoteError` | verified |
| 21 | Runtime status | `返回` (detail modal) | `frontend/src/RuntimeStatusPanel.tsx:893` | `onClick` → `setView('root')` | — | — | — | Returns to the detail root pane | `view → 'root'` | none observed in code | frontend-only |
| 22 | Runtime status | `停止共享池` (advanced) | `frontend/src/RuntimeStatusPanel.tsx:913` | `onClick` → `stopPool(false)` (`:729-741`) | `api.stopPool` (`api.ts:173`) then `api.pool` (`api.ts:172`) | `POST /api/pool/stop` — `src/web/pool_api.py:52`; `GET /api/pool` — `pool_api.py:22` | `stop_pool` (`pool_api.py:52-56`); `pool` (`pool_api.py:23-51`) | Stops the managed shared pool gracefully, then refetches the pool block | pool `active[] → []`; `instance.closing` set | `409` `PoolClientError`; no `window.confirm` on the graceful variant | verified |
| 23 | Runtime status | `强制清除共享池` (advanced) | `frontend/src/RuntimeStatusPanel.tsx:914` | `onClick` → `stopPool(true)` (`:729-741`) with `window.confirm` (`:730`) | `api.stopPool` (`api.ts:173`) | `POST /api/pool/stop` — `src/web/pool_api.py:52` | `stop_pool` (`pool_api.py:52-56`) | Force-kills pool workers; in-flight jobs are lost | `active[] → []` | `409` `PoolClientError`; browser confirm gate | verified |
| 24 | Runtime status | `停止共享池` (remote block) | `frontend/src/RuntimeStatusPanel.tsx:937` | `onClick` → `stopRemote(id, false)` (`:743-755`) | `api.remotePoolStop` (`api.ts:175`) | `POST /api/remote/{key}/pool/stop` — `src/web/remote_api.py:136` | `remote_pool_stop` (`remote_api.py:137`) | Stops the pool on the remote host | remote pool `active[] → []` | `409`/`422` `RemoteError` | verified |
| 25 | Runtime status | `查看远程环境` | `frontend/src/RuntimeStatusPanel.tsx:939` | `onClick` → `loadRemote` (`:757-768`) | `api.remoteEnvironments` (`api.ts:178`) | `GET /api/remote/{key}/environments` — `src/web/remote_api.py:82` | `remote_environments` (`remote_api.py:83-85`) | Loads the remote environment list into the advanced block | advanced block `empty → populated` | `409`/`422` `RemoteError` | verified |
| 26 | Runtime status | `准备远程环境` | `frontend/src/RuntimeStatusPanel.tsx:941` | `onClick` → `prepareRemote` (`:770-781`) | `api.remotePrepareEnvironments` (`api.ts:180`) | `POST /api/remote/{key}/environments/prepare` — `src/web/remote_api.py:86` | `remote_prepare_environments` (`remote_api.py:86`) | Enqueues installs on the remote host for the advanced block's profile | remote envs `queued → installing` | `409`/`422` `RemoteError` | verified |
| 27 | Runtime status | Environment row inside readiness list (no handler) | `frontend/src/RuntimeStatusPanel.tsx:368-376` | rendered from `availableActions(item.status)` (`:144-151`) | — | — | — | Action set is derived from status only; `ready` yields no buttons | `ready` → zero actions | n/a | frontend-only |
| 28 | Large resources | `刷新` | `frontend/src/LargeResourceSection.tsx:266` | `onClick` → `load()` (`:156-169`) | `api.largeResources` (`api.ts:236`) / `api.remoteResources` (`api.ts:192`) | `GET /api/resources` — `src/web/resource_api.py:893`; remote `GET /api/remote/{key}/resources` — `remote_api.py:107` | `resources` (`resource_api.py:894-899`); `remote_resources` (`remote_api.py:108`) | Re-reads the resource catalogue, unit coverage and the last 20 operations | `idle → loading`; unit rows re-rendered | `409` on `ValueError` (`resource_api.py:893`); remote `409`/`422` | verified |
| 29 | Large resources | `全部安装` | `frontend/src/LargeResourceSection.tsx:267` | `onClick` → `downloadAll()` (`:213-221`) | `api.largeResourceDownload` (`api.ts:243`) / `api.remoteResourceDownload` (`api.ts:246`) | `POST /api/resources/{name}/download` — `src/web/resource_api.py:900`; remote `POST /api/remote/{key}/resources/{name}/download` — `remote_api.py:119` | `download` (`resource_api.py:900-910`); `remote_resource_download` (`remote_api.py:120`) | Fires one download job per resource unit that is not already ready; units already complete are skipped client-side | each unit `missing → downloading → present` | `404` `unknown resource`; `409` | verified |
| 30 | Large resources | `解除链接` (unit card) | `frontend/src/LargeResourceSection.tsx:111` | `onUnlink` → `unlink` (`:206-211`) | `api.largeResourceUnlink` (`api.ts:240`) / `api.remoteUnlinkResource` (`api.ts:198`) | `DELETE /api/resources/{name}/link?unit=` — `src/web/resource_api.py:925`; remote `DELETE /api/remote/{key}/resources/{name}/link` — `remote_api.py:128` | `unlink` (`resource_api.py:925-935`); `remote_unlink` (`remote_api.py:129`) | Removes the symlink/link for that unit; the unit state degrades to `missing` | unit `linked → missing` | `404`; **`501` on `LinkUnsupported`**; `409` | verified |
| 31 | Large resources | Download button — label is `下载可用文件（have/total）`, or `rsync 拉取`, or `无下载源` | `frontend/src/LargeResourceSection.tsx:115-130` | `onDownload` → `download` (`:199-204`) | `api.largeResourceDownload` (`api.ts:243`) / `api.remoteResourceDownload` (`api.ts:246`) | `POST /api/resources/{name}/download` — `resource_api.py:900`; remote — `remote_api.py:119` | `download` (`resource_api.py:900-910`) | Starts the download for one unit. The button is disabled when `download_supported === false && !rsync` (`:115-130`), i.e. the `无下载源` state is decided purely from the catalogue payload | unit `missing → downloading → present`; disabled state driven by `unit.download_supported` (`resource_api.py:360`) | `404`; `409`; nothing to click when disabled | degraded |
| 32 | Large resources | `链接` (unit card) | `frontend/src/LargeResourceSection.tsx:131` | `onLink` → `setLink` (`:283`) | — | — | — | Opens the link modal pre-filled with the unit's component | `link: null → {resource, component}` | none observed in code | frontend-only |
| 33 | Large resources | `源路径` (text input, link modal) | `frontend/src/LargeResourceSection.tsx:301` | `onChange` → `setSource` | — | — | — | Holds the path that row 36 will submit | `source: string` | none observed in code | frontend-only |
| 34 | Large resources | `浏览…` (link modal) | `frontend/src/LargeResourceSection.tsx:303` | `onClick` → `loadPicker(source.trim())` (`:304`) | `api.browsePath` (`api.ts:233`) / `api.browseRemote` (`api.ts:235`) | `POST /api/browse` — `src/web/resource_api.py:885`; remote `POST /api/remote/{key}/browse` — `remote_api.py:155` | `browse` (`resource_api.py:886-892`); `remote_browse` (`remote_api.py:156`) | Lists one directory (max 500 entries); returns `{path, parent, roots, entries[]}` | picker `closed → open`, `path` moves on each navigation | `409` on `ValueError`; remote `409`/`422` | verified |
| 35 | Large resources | `取消` (link modal) | `frontend/src/LargeResourceSection.tsx:313` | `onClick` → `setLink(null)` | — | — | — | Discards the modal | `link → null` | none observed in code | frontend-only |
| 36 | Large resources | `链接` (link modal submit) | `frontend/src/LargeResourceSection.tsx:314` | `onClick` → `submitLink` (`:246-255`) | `api.largeResourceLink` (`api.ts:237`) / `api.remoteLinkResource` (`api.ts:194`) | `POST /api/resources/{name}/link` — `src/web/resource_api.py:911`; remote `POST /api/remote/{key}/resources/{name}/link` — `remote_api.py:111` | `link` (`resource_api.py:911-924`); `remote_link` (`remote_api.py:112`) | Creates the link with `replace=true` and the component name as `unit`; mutates the resource manifest on disk | unit `missing → linked` | `404`; **`501` `LinkUnsupported`**; `409` | verified |
| 37 | Large resources | `上级` (picker) | `frontend/src/LargeResourceSection.tsx:324` | `onClick` → `loadPicker(picker.parent)` (`:223-244`) | `api.browsePath` (`api.ts:233`) / `api.browseRemote` (`api.ts:235`) | as row 34 | as row 34 | Directory navigation only | `picker.path` moves up | `409` | verified |
| 38 | Large resources | Drive/root buttons (picker) | `frontend/src/LargeResourceSection.tsx:331` | `onClick` → `loadPicker(root)` | `api.browsePath` (`api.ts:233`) | `POST /api/browse` — `src/web/resource_api.py:885` | `browse` (`resource_api.py:886-892`) | Jumps to a filesystem root; roots come from `_drive_roots()` in the browse payload (`resource_api.py:845-881`) | `picker.path` = root | `409` | verified |
| 39 | Large resources | Directory entry (picker) | `frontend/src/LargeResourceSection.tsx:340` | `onClick` → `loadPicker(entry.path)` | `api.browsePath` (`api.ts:233`) | `POST /api/browse` — `resource_api.py:885` | `browse` (`resource_api.py:886-892`) | Descends into a directory | `picker.path` | `409` | verified |
| 40 | Large resources | File entry (picker) | `frontend/src/LargeResourceSection.tsx:340` | `onClick` → `setSource(entry.path)` + close picker | — | — | — | Chooses a file path without a request | `source` set, picker closed | none observed in code | frontend-only |
| 41 | Large resources | `取消` (picker) | `frontend/src/LargeResourceSection.tsx:358` | `onClick` → close picker | — | — | — | Closes the picker | `picker → null` | none observed in code | frontend-only |
| 42 | Large resources | `选择此文件夹` (picker) | `frontend/src/LargeResourceSection.tsx:360` | `onClick` → `setSource(picker.path)` + close | — | — | — | Copies the current directory into the source field | `source` set | none observed in code | frontend-only |
| 43 | Settings → Servers | `关闭服务器面板` (icon) | `frontend/src/RemotePanel.tsx:92` | `onClick` → `onClose` | — | — | — | Closes the panel | panel unmounted | none observed in code | frontend-only |
| 44 | Settings → Servers | Saved-server row (button) | `frontend/src/RemotePanel.tsx:94` | `onClick` → `setProfile(item)` | — | — | — | Loads a saved profile into the form | `profile` replaced | none observed in code | frontend-only |
| 45 | Settings → Servers | `添加服务器` | `frontend/src/RemotePanel.tsx:97` | `onClick` → blank profile | — | — | — | Clears the form for a new profile | `profile = {}` | none observed in code | frontend-only |
| 46 | Settings → Servers | `浏览已配置文件` | `frontend/src/RemotePanel.tsx:98` | `onClick` → `setFiles(true)` → `StorageFilePicker` (`:154`) | `api.storageRoots`/`api.browseStorage` (via `StorageFilePicker`) | `GET /api/v1/storage/roots` — `operon/storage_api.py:83`; `POST /api/v1/storage/browse` — `storage_api.py:89` | `storage_roots` (`storage_api.py:83-88`); `storage_browse` (`storage_api.py:90-92`) | Server-side directory picker for `~/.ssh/config` style files | picker `closed → open` | `409`/`422` from the storage layer | verified |
| 47 | Settings → Servers | `名称` / `主机` / `用户名` / `Python` / `Operon 目录` / `运行目录` / `本机私钥路径` / `实例编号` / `安装目录` (9 inputs via `field()`) | `frontend/src/RemotePanel.tsx:88-90` | `onChange` → `setProfile` | — (submitted by row 64/58) | — | — | Populates the profile payload sent to `POST /api/remote/profiles` | `profile.*` | none observed in code | frontend-only |
| 48 | Settings → Servers | `端口` (number input) | `frontend/src/RemotePanel.tsx:102` | `onChange` → `setProfile` | — | — | — | `profile.port` used by connect/install | `profile.port` | none observed in code | frontend-only |
| 49 | Settings → Servers | `服务器环境` (select: managed/existing) | `frontend/src/RemotePanel.tsx:103` | `onChange` → `setProfile` | — | — | — | Chooses whether the remote gets a managed venv or an existing interpreter | `profile.environment` | none observed in code | frontend-only |
| 50 | Settings → Servers | `认证方式` (select: password/key/agent) | `frontend/src/RemotePanel.tsx:107` | `onChange` → `setProfile` | — | — | — | Selects the SSH auth branch; drives which credential field is shown | `profile.auth` | none observed in code | frontend-only |
| 51 | Settings → Servers | `密码` (password input) | `frontend/src/RemotePanel.tsx:109` | `onChange` → `setProfile` | — (sent as `{password}` by rows 58/64) | — | — | Held in memory only; never persisted by `saveRemote` | `profile.password` | none observed in code | frontend-only |
| 52 | Settings → Servers | `私钥口令` (password input) | `frontend/src/RemotePanel.tsx:110` | `onChange` → `setProfile` | — (sent as `{passphrase}`) | — | — | Held in memory only | `profile.passphrase` | none observed in code | frontend-only |
| 53 | Settings → Servers | `登录方式` (select: exec/shell) | `frontend/src/RemotePanel.tsx:113` | `onChange` → `setProfile` | — | — | — | Chooses the SSH channel used to bootstrap the remote engine | `profile.login` | none observed in code | frontend-only |
| 54 | Settings → Servers | `实例编号` (input) | `frontend/src/RemotePanel.tsx:114` | `onChange` → `setProfile` | — | — | — | Selects which remote instance to reuse | `profile.instance` | none observed in code | frontend-only |
| 55 | Settings → Servers | `强制升级` (checkbox) | `frontend/src/RemotePanel.tsx:118` | `onChange` → `setForceUpgrade` | — (read by row 58) | — | — | Forces `force:true` on install | `forceUpgrade` | none observed in code | frontend-only |
| 56 | Settings → Servers | `安装 / 升级服务端` / `强制升级服务端` | `frontend/src/RemotePanel.tsx:121` | `onClick` → `connect('install', undefined, forceUpgrade)` (`:124`), guarded by `reportValidity()` (`:122`) and `window.confirm` (`:123`) | `api.saveRemote` (`api.ts:219`) → `api.installRemote` (`api.ts:221`) | `POST /api/remote/profiles` — `src/web/remote_api.py:31`; `POST /api/remote/{key}/install` — `remote_api.py:39` | `save_remote` (`remote_api.py:32-34`); `install_remote` (`remote_api.py:40-46`) | Persists the profile, then uploads/installs the engine on the remote host; returns a job-like status that the panel polls via `api.remoteSetup` (`:35`) | `busy: 'install'`; setup status polled every 1500 ms | `409` `host_key_required` → trust prompt (`:75-76`); `422` `server_not_installed`/`server_incompatible`/`handshake_incompatible`/`capability_missing`/`stale_build`/`build_changed` (`showError` `:45-61`) | verified |
| 57 | Settings → Servers | Trust fingerprint confirm button | `frontend/src/RemotePanel.tsx:129` | `onClick` → `connect(trust.action, trust, trust.force)` | `api.trustRemote` (`api.ts:230`) | `POST /api/remote/{key}/trust` — `src/web/remote_api.py:140` | `trust_remote` (`remote_api.py:141-144`) | Stores the host key fingerprint and returns `{trusted:true}` | trust prompt closed; connect/install retried | `409`/`422` `RemoteError` | verified |
| 58 | Settings → Servers | `连接服务器` (form submit) | `frontend/src/RemotePanel.tsx:149` | `onSubmit` (`:99`) → `connect('connect')` (`:62-80`) | `api.saveRemote` (`api.ts:219`) → `api.connectRemote` (`api.ts:220`) | `POST /api/remote/profiles` — `remote_api.py:31`; `POST /api/remote/{key}/connect` — `remote_api.py:35` | `save_remote` (`remote_api.py:32-34`); `connect_remote` (`remote_api.py:36-38`) | Saves the profile then opens an SSH/engine session; on success the remote appears in the execution-position selector | `busy: 'connect' → idle`; profile list refreshed | `409` `host_key_required`; `422` handshake/capability codes as row 56 | verified |
| 59 | Settings → Servers | `刷新算子与依赖` | `frontend/src/RemotePanel.tsx:134` | `onClick` → `refresh()` (`:81-87`) | `api.refreshRemote` (`api.ts:222`) | `POST /api/remote/{key}/refresh` — `src/web/remote_api.py:47` | `refresh_remote` (`remote_api.py:48-53`) | Re-reads remote version/build/capabilities (`verify_all` flag) and updates the profile's status | profile `build`/`capabilities` refreshed | `409`/`422` `RemoteError` | verified |
| 60 | Settings → Servers | `取消安装` / `取消连接` | `frontend/src/RemotePanel.tsx:146` | `onClick` → `api.disconnectRemote(profile.id)` | `api.disconnectRemote` (`api.ts:231`) | `POST /api/remote/{key}/disconnect` — `src/web/remote_api.py:145` | `disconnect_remote` (`remote_api.py:146`) | Aborts the in-flight install/connect by tearing down the session; returns `{disconnected:true}` | `busy → idle` | `409`/`422` `RemoteError` | verified |
| 61 | Settings → Servers | `断开` | `frontend/src/RemotePanel.tsx:147` | `onClick` → `api.disconnectRemote` then `onUpdate` | `api.disconnectRemote` (`api.ts:231`) | as row 60 | as row 60 | Drops the session and refreshes the parent list | profile `connected:false` | `409`/`422` | verified |
| 62 | Settings → Servers | `移除` | `frontend/src/RemotePanel.tsx:148` | `onClick` → `api.removeRemote(profile.id)` | `api.removeRemote` (`api.ts:232`) | `POST /api/remote/{key}/remove` — `src/web/remote_api.py:150` | `remove_remote` (`remote_api.py:151-154`) | Deletes the profile from the local registry; returns `{removed:true}` | profile row disappears | `409`/`422` | verified |
| 63 | Settings → Servers | `上级目录` (remote file picker) | `frontend/src/RemotePanel.tsx:183` | `onClick` → `browse(listing.parent)` | `api.browseRemote` (`api.ts:235`) | `POST /api/remote/{key}/browse` — `src/web/remote_api.py:155` | `remote_browse` (`remote_api.py:156-158`) | Lists a remote directory | `listing.path` moves up | `409`/`422` | verified |
| 64 | Settings → Servers | Directory input + `打开目录` (remote file picker) | `frontend/src/RemotePanel.tsx:184` | `onSubmit` → `browse(path)` | `api.browseRemote` (`api.ts:235`) | as row 63 | as row 63 | Jumps to a typed remote path | `listing.path` | `409`/`422` | verified |
| 65 | Settings → Servers | Entry row (remote file picker) | `frontend/src/RemotePanel.tsx:187` | `onClick` → directory ? `browse(entry.path)` : `setSelected(entry)`; `onDoubleClick` → `choose` (`:188`) | `api.browseRemote` (`api.ts:235`) on directories | as row 63 | as row 63 | Navigation, or selection of a file | `selected` | `409`/`422` | verified |
| 66 | Settings → Servers | `加载更多` (remote file picker) | `frontend/src/RemotePanel.tsx:192` | `onClick` → `browse(listing.path, listing.next_offset)` | `api.browseRemote` (`api.ts:235`) | as row 63 | as row 63 | Pages the remote directory listing | `listing.next_offset` advances | `409`/`422` | verified |
| 67 | Settings → Servers | `显示隐藏文件` (checkbox) | `frontend/src/RemotePanel.tsx:195` | `onChange` → `setHidden` | `api.browseRemote` with the hidden flag | as row 63 | as row 63 | Refetches the listing including dotfiles | `hidden: bool` | `409`/`422` | verified |
| 68 | Settings → Servers | `选择文件` (remote file picker) | `frontend/src/RemotePanel.tsx:195` | `onClick` → `choose(selected)` (`:175-179`) | `api.sourceRemote` (`api.ts:264`) when the picker is in `source` mode | `POST /api/remote/{key}/source` — `src/web/remote_api.py:159` | `remote_source` (`remote_api.py:160-162`) → `manager.call(key,'source',payload)` | Resolves a remote path into a readable source descriptor (path + reader) for the caller | picker closed; caller receives `(value, source)` | `409`/`422` `RemoteError` | verified |
| 69 | Settings → Servers | `检查算子库` (remote library) | `frontend/src/RemoteLibraryPanel.tsx:78` | `onClick` → `inspect()` (`:41-47`) | `api.checkRemoteLibrary` (`api.ts:223`) | `POST /api/remote/{key}/library/check` — `src/web/remote_api.py:62` | `check_remote_library` (`remote_api.py:63-65`) | Compares the remote operator library against the local registry | `state: idle → checking → {status}` | `409`/`422`; auto-run at mount when no `initial` (`:35-39`) | verified |
| 70 | Settings → Servers | `强制同步算子库` | `frontend/src/RemoteLibraryPanel.tsx:118` | `onClick` → `inspectPlan()` (`:48-54`) | `api.remoteLibraryPlan` (`api.ts:227`) | `GET /api/remote/{key}/library/plan` — `src/web/remote_api.py:74` | `remote_library_plan` (`remote_api.py:75-77`) | Computes the diverging files without applying them | `plan` rendered | `409`/`422` | verified |
| 71 | Settings → Servers | `开始强制同步` | `frontend/src/RemoteLibraryPanel.tsx:106` | `onClick` → `sync()` (`:69-74`) then `poll()` (`:55-68`) | `api.syncRemoteLibrary` (`api.ts:228`), then `api.remoteLibraryStatus` (`api.ts:226`) | `POST /api/remote/{key}/library/sync` — `remote_api.py:70`; `GET /api/remote/{key}/library/status` — `remote_api.py:78` | `remote_library_sync` (`remote_api.py:71-73`); `remote_library_status` (`remote_api.py:79-81`) | Overwrites the remote library with local files, then polls progress until `complete` | `syncing → complete` (`:62` re-checks on completion) | `409`/`422` | verified |
| 72 | Settings → Servers | `取消` (sync plan) | `frontend/src/RemoteLibraryPanel.tsx:108` | `onClick` → `setPlan(undefined)` | — | — | — | Discards the computed plan | `plan → undefined` | none observed in code | frontend-only |
| 73 | Settings → Servers | `安装 / 升级服务端` (remote library panel) | `frontend/src/RemoteLibraryPanel.tsx:120` | `onClick` → `onInstall` → `RemotePanel.connect('install')` | as row 56 | as row 56 | as row 56 | Delegates to the install flow | as row 56 | as row 56 | verified |
| 74 | Settings → Output & viewers | `程序位置` (input per viewer) | `frontend/src/ViewerSettings.tsx:14` | `onChange` → `setPath` | — (submitted by row 76) | — | — | Holds the viewer executable path | `path` | none observed in code | frontend-only |
| 75 | Settings → Output & viewers | `恢复自动检测` | `frontend/src/ViewerSettings.tsx:15` | `onClick` → `save(viewer.id, null)` | `api.configureViewer` (`api.ts:211`) | `POST /api/v1/viewers/{viewer}/configure` — `operon/viewer_api.py:41` | `configure_viewer` (`viewer_api.py:42-45`) | Clears the stored path so auto-detection applies | viewer `configured_path → null` | `409`/`422` viewer errors; `busy` disables the button when no path is stored | verified |
| 76 | Settings → Output & viewers | `保存位置` (submit) | `frontend/src/ViewerSettings.tsx:16` | form submit → `save(viewer.id, path)` (`:66`) | `api.configureViewer` (`api.ts:211`) | as row 75 | as row 75 | Persists the chosen executable path | viewer `status: missing → ready` (or stays `unsupported_system`) | disabled for `unsupported_system`; errors surface in the section message | verified |
| 77 | Settings → Output & viewers | `重新检测` | `frontend/src/ViewerSettings.tsx:40` | `onClick` → `update(() => api.viewers(true))` | `api.viewers` (`api.ts:210`) | `GET /api/v1/viewers?refresh=` — `operon/viewer_api.py:31` | `list_viewers` (`viewer_api.py:32-35`) | Re-probes installed viewers and the file-format catalogue | catalogue reloaded; message `已重新检测` | `409`/`422` | verified |
| 78 | Settings → Output & viewers | `文件格式` (select) | `frontend/src/ViewerSettings.tsx:45` | `onChange` → `setExtension` + `setChoice(defaults[ext])` | — | — | — | Selects the format being configured | `extension`, `choice` | none observed in code | frontend-only |
| 79 | Settings → Output & viewers | `打开方式` (select) | `frontend/src/ViewerSettings.tsx:48` | `onChange` → `setChoice` | — (submitted by row 80) | — | — | Selects the default viewer for the format | `choice` | none observed in code | frontend-only |
| 80 | Settings → Output & viewers | `保存` (default viewer submit) | `frontend/src/ViewerSettings.tsx:53` | form submit → `api.defaultViewer(extension, choice)` (`:44`) | `api.defaultViewer` (`api.ts:212`) | `POST /api/v1/viewers/default` — `operon/viewer_api.py:36` | `set_default_viewer` (`viewer_api.py:37-40`) | Writes the default-viewer mapping | format row updates to the new viewer | disabled unless `currentExists`; `409`/`422` | verified |
| 81 | Settings → Output & viewers | Saved suffix row (button) | `frontend/src/ViewerSettings.tsx:57` | `onClick` → `setExtension(suffix)` + `setChoice(id)` | — | — | — | Loads a saved mapping into the form | `extension`, `choice` | none observed in code | frontend-only |
| 82 | Settings → Output & viewers | `清除 {suffix} 默认打开方式` (icon) | `frontend/src/ViewerSettings.tsx:58` | `onClick` → `update(() => api.defaultViewer(suffix, null))` | `api.defaultViewer` (`api.ts:212`) | `POST /api/v1/viewers/default` — `operon/viewer_api.py:36` | `set_default_viewer` (`viewer_api.py:37-40`) | Removes the mapping so auto-selection applies | mapping row disappears; message `已恢复自动选择` | `409`/`422` | verified |
| 83 | Settings → Output & viewers | `搜索查看器` (input) | `frontend/src/ViewerSettings.tsx:64` | `onChange` → `setSearch` | — | — | — | Filters the viewer/format list client-side | `search` | none observed in code | frontend-only |
| 84 | Files / top bar | `重新加载` (boot-error screen) | `frontend/src/App.tsx:175` | `onClick={() => location.reload()}` | — | — | — | Full page reload | n/a | none observed in code | frontend-only |
| 85 | Files / top bar | `重新连接` (connection-lost screen) | `frontend/src/App.tsx:1254` | `onClick` → `load()` (`:597`) | `api.bootstrap` (`api.ts:384`) | `GET /api/bootstrap` — `src/web/api.py:147` | `bootstrap` (`api.py:147-165`) | Refetches the bootstrap payload (token, catalog generation, demo graph, preferences) and stores the studio token used as `x-studio-token` afterwards | `disconnected → ready`; whole app repopulated | middleware 403 `本地会话已更新，请刷新页面。` if the token rotated; otherwise 500 handler (`api.py:110`) | verified |
| 86 | Files / top bar | `保存路线` (icon) | `frontend/src/App.tsx:1285` | `onClick` → `save` (`:1165`) | — (opens `SaveWorkflowDialog`, submitted by row 91) | — | — | Clones the graph into dialog state; no request until the dialog is submitted | `saveDialog: null → graph` | none observed in code | frontend-only |
| 87 | Files / top bar | `设置` (icon) | `frontend/src/App.tsx:1293` | `onClick` → `setAppSettings('servers')` | — | — | — | Opens the settings modal on the Servers section | `appSettings: null → 'servers'` | none observed in code | frontend-only |
| 88 | Files / top bar | `文件` (menu toggle) | `frontend/src/App.tsx:1295` | `onClick` → `setExportOpen(!exportOpen)` | — | — | — | Opens the file menu | `exportOpen: bool` | none observed in code | frontend-only |
| 89 | Files / top bar | `关闭文件菜单` (scrim, `aria-label`) | `frontend/src/App.tsx:1306` | `onClick` → `setExportOpen(false)` | — | — | — | Closes the menu | `exportOpen → false` | none observed in code | frontend-only |
| 90 | Files / top bar | `打开已保存画布` | `frontend/src/App.tsx:1312` | `onClick` → `setPicker('open')` | `api.workflows` (`api.ts:325`) issued by `WorkflowPicker` (`RouteDialogs.tsx:45`) | `GET /api/workflows` — `src/web/api.py:175` | `workflows` (`api.py:175-179`) | Lists saved routes; selecting one calls `api.workflow(id)` (`RouteDialogs.tsx:50`) → `GET /api/workflows/{key}` (`api.py:253`) | picker `closed → open`; `pending` while loading | load errors land in the dialog error line (`RouteDialogs.tsx:45`) | verified |
| 91 | Files / top bar | `保存路线与接口` (and dialog `保存路线`) | `frontend/src/App.tsx:1313` | `onClick` → `save()`; submit in `SaveWorkflowDialog.save` → `api.saveWorkflow(draft, id, version)` (`RouteDialogs.tsx:83`) | `api.saveWorkflow` (`api.ts:346`) | `POST /api/workflows/save` — `src/web/api.py:241` | `save_workflow` (`api.py:241-252`) | Persists graph, port labels and interface contract; bumps `workflow_version` unless `另存为新路线` (`RouteDialogs.tsx:101`) | `version → version+1`; dialog closes on success | `409` stale `expected_version` (`RouteLibrary.save` rejects with `路线已在其他页面更新...`); `422` invalid interface | verified |
| 92 | Files / top bar | `导入路线 / YAML / JSON` | `frontend/src/App.tsx:1314` | `onClick` → `importInput.current.click()` | — (opens the file dialog at row 108) | — | — | Triggers the hidden file input | none | none observed in code | frontend-only |
| 93 | Files / top bar | `YAML 输入相对目录` (input) | `frontend/src/App.tsx:1324` | `onChange` → `setImportBase` | — | — | — | Sets the base directory passed to `api.import(text, base)` (row 108) | `importBase` | none observed in code | frontend-only |
| 94 | Files / top bar | `导出路线包` | `frontend/src/App.tsx:1330` | `onClick` → `api.exportWorkflow(graph)` (`:1333`) | `api.exportWorkflow` (`api.ts:328`) | `POST /api/workflows/export` — `src/web/api.py:183` | `export_workflow` (`api.py:183-186`) | Serialises the canvas into a route package and triggers a download | `exportOpen → false` | `422` `ManifestError`/`GraphError`; 500 handler | verified |
| 95 | Files / top bar | `导出执行 YAML` | `frontend/src/App.tsx:1338` | `onClick` → `exportYaml()` (`:1153`) | `api.export` (`api.ts:392`) | `POST /api/export` — `src/web/api.py:295` | `export_workflow` (`api.py:295-306`) | Builds `pipeline.yaml` and downloads it | none | `422`; 500 handler | verified |
| 96 | Files / top bar | `导出可编辑 YAML 项目` | `frontend/src/App.tsx:1340` | `onClick` → `api.exportWorkflow(graph,'yaml')` (`:1342`) | `api.exportWorkflow` (`api.ts:328`) | `POST /api/workflows/export-yaml` — `src/web/api.py:188` | `export_workflow_yaml` (`api.py:188-194`) | Exports a directory-shaped YAML project archive | none | `422`; 500 handler | verified |
| 97 | Files / top bar | `导出独立运行包` | `frontend/src/App.tsx:1345` | `onClick` → `setCanvasPlan('export')` | — (row 149 issues the POST) | — | — | Opens the export dialog; the POST happens inside `CanvasPlanDialog` | `canvasPlan: null → 'export'` | none observed in code | frontend-only |
| 98 | Files / top bar | `载入分支示例` | `frontend/src/App.tsx:1347` | `onClick` → `openPages([normalizeGraph(bootstrap.demo)])` | — | — | — | Opens the bundled demo graph as a new document | new document page | none observed in code | frontend-only |
| 99 | Files / top bar | `新建空白工作流` | `frontend/src/App.tsx:1357` | `onClick` → `newPage()` | — | — | — | Creates an empty document | new document page | none observed in code | frontend-only |
| 100 | Files / top bar | `恢复关闭的页面` | `frontend/src/App.tsx:1365` | `onClick` → `reopenPage()` | — | — | — | Restores the last closed document from the in-memory stack | closed-page stack pops | disabled when the stack is empty | frontend-only |
| 101 | Files / top bar | `Agent` | `frontend/src/App.tsx:1371` | `onClick` → `setAgentPanel(true)` | — | — | — | Opens the agent panel (its own controls were outside the read set) | `agentPanel: bool` | none observed in code | frontend-only |
| 102 | Files / top bar | `执行位置` (select, per-canvas execution host) | `frontend/src/App.tsx:1375` | `onChange` → `chooseServer(e.target.value)` (`:215`) | — | — | — | Rewrites the graph's execution target; no request | graph `execution.target` | disabled while `busy` | frontend-only |
| 103 | Files / top bar | `检查` | `frontend/src/App.tsx:1381` | `onClick` → `validate()` (`:1075-1098`) | `api.validate` (`api.ts:389`) | `POST /api/validate` — `src/web/api.py:279` | `validate` (`api.py:279-282`) | Validates the canvas; UI reads `result.readiness.status` and `result.order` | `validation: null → report`; drives the run button | `422` `ManifestError`/`GraphError` rendered as a notice | verified |
| 104 | Files / top bar | `任务` | `frontend/src/App.tsx:1387` | `onClick` → `setTab('tasks')` + expand results | — | — | — | Switches the results dock to the task list | `tab: 'tasks'`; `resultsCollapsed: false` | none observed in code | frontend-only |
| 105 | Files / top bar | `执行计划` | `frontend/src/App.tsx:1390` | `onClick` → `setPlanPanel(true)` | — (PlanPanel issues its own requests) | — | — | Opens the plan panel | `planPanel: bool` | none observed in code | frontend-only |
| 106 | Files / top bar | `路线运行与导出记录` | `frontend/src/App.tsx:1391` | `onClick` → `setCanvasPlan('history')` | GET `/api/v1/canvas-plans/history` issued by the dialog (`CanvasPlanDialog.tsx:31`) | `operon/canvas_api.py:49` | `history` (`canvas_api.py:50-53`) | Lists past canvas preparations/exports | `canvasPlan: 'history'` | `403` when the actor lacks `context` (`operon/bridge.py:51-65`) | verified |
| 107 | Files / top bar | `运行` | `frontend/src/App.tsx:1392` | `onClick` → `run()` (`:1099-1117`) | — (no request; opens `CanvasPlanDialog` with `intent='run'`) | — | — | Checks for duplicate output paths, then defers to the dialog, which calls `/api/v1/canvas-plans/prepare` (rows 148-149) | `canvasPlan: 'run'` | none observed in code | frontend-only |
| 108 | Files / top bar | `导入工作流文件` (file input, `aria-label`) | `frontend/src/App.tsx:1403` | `onChange` → `importFile` (`:1130-1152`) | `api.importWorkflow` (`api.ts:338`) / `api.import` (`api.ts:394`) | `POST /api/workflows/import` — `src/web/api.py:195`; `POST /api/import` — `api.py:307` | `import_workflow` (`api.py:195-207`); `import_workflow_text` (`api.py:307-336`) | Parses a route package or YAML/JSON text and opens it as a document | new document page | `422` `ManifestError` on malformed input; 500 handler | verified |
| 109 | Files / top bar | `导入路线包或 JSON` (file input, multiple) | `frontend/src/App.tsx:1411` | `onChange` → `importRoutes` (`:559-569`) | `api.importWorkflow` (`api.ts:338`) then `api.saveWorkflow` (`api.ts:346`) | `POST /api/routes/import-archive` — `src/web/api.py:208`; `POST /api/workflows/save` — `api.py:241` | `import_route_archive` (`api.py:208-240`); `save_workflow` (`api.py:241-252`) | Imports each archive and immediately persists it into the route library | route list refreshed via `refreshRoutes` | `422` invalid archives; `409` stale `expected_version` | verified |
| 110 | Operator library | `关闭工具面板` (`aria-label`) | `frontend/src/App.tsx:1415` | `onClick` → closes the drawer | — | — | — | Closes the drawer | drawer `open → closed` | none observed in code | frontend-only |
| 111 | Operator library | `算子库来源` (select) | `frontend/src/App.tsx:1431` | `onChange` → `setLibrarySource` | — | — | — | Filters which catalog source is shown | `librarySource` | none observed in code | frontend-only |
| 112 | Operator library | `添加算子` (icon) | `frontend/src/App.tsx:1435` | `onClick` → `setPluginsOpen('add')` | — | — | — | Opens `PluginPanel` on its add tab | `pluginsOpen: 'add'` | none observed in code | frontend-only |
| 113 | Operator library | `刷新算子库` (icon) | `frontend/src/App.tsx:1436` | `onClick` → `refreshPlugins()` (`:516-543`) | `api.refreshPlugins` (`api.ts:266`), polled with `api.pluginOperation` (`api.ts:269`), then `api.catalog` (`api.ts:319`) | `POST /api/plugins/refresh` — `src/web/plugin_api.py:108`; `GET /api/plugins/operations/{key}` — `plugin_api.py:102`; `GET /api/operators` — `src/web/api.py:273` | `refresh_plugins` (`plugin_api.py:108-114`); `plugin_operation` (`plugin_api.py:102-107`); `operators` (`api.py:273-278`) | Rescans plugin/operator declarations and swaps the catalog | `refreshingPlugins: bool`; catalog generation bumped | poll errors abort the loop and surface as a toast; `409` if a refresh is already running | verified |
| 114 | Operator library | `关闭算子库` (`aria-label`) | `frontend/src/App.tsx:1437` | `onClick` → `setLibraryOpen(false)` | — | — | — | Closes the drawer | `libraryOpen → false` | none observed in code | frontend-only |
| 115 | Operator library | `搜索算子与 Reader` (input) | `frontend/src/App.tsx:1447` | `onChange` → `setSearch` | — | — | — | Client-side filter | `search` | none observed in code | frontend-only |
| 116 | Operator library | `已删除` / `收起已删除` (toggle) | `frontend/src/App.tsx:1455` | `onClick` → `setShowHidden(v => !v)` | — | — | — | Reveals library entries hidden by `delete`/`disable` | `showHidden: bool` | none observed in code | frontend-only |
| 117 | Operator library | `输入数据` | `frontend/src/App.tsx:1456` | `onClick` → `add()` (`:982`) | — | — | — | Adds an input-data node | graph nodes + revision bump | none observed in code | frontend-only |
| 118 | Operator library | Reader list item | `frontend/src/App.tsx:1474` | `onClick` → `add('reader:'+id)` | — | — | — | Adds the Reader node | graph nodes | none observed in code | frontend-only |
| 119 | Operator library | `添加已保存路线` (empty-state) | `frontend/src/App.tsx:1485` | `onClick` → `setPluginsOpen('add')` | — | — | — | Opens the add-panel | `pluginsOpen: 'add'` | none observed in code | frontend-only |
| 120 | Operator library | Saved-route item | `frontend/src/App.tsx:1488` | `onClick` → `add(route.id)`; `onContextMenu` → `setContextMenu({route, libraryKey})` | — | — | — | Inserts the route as a node, or opens the context menu | graph nodes / `contextMenu` | disabled when the entry is library-disabled | frontend-only |
| 121 | Operator library | Operator item | `frontend/src/App.tsx:1499` | `onClick` → `add(spec.id)`; `onContextMenu` → `setContextMenu({libraryKey})` | — | — | — | Inserts the operator node, or opens the context menu | graph nodes / `contextMenu` | none observed in code | frontend-only |
| 122 | Operator library | `清空搜索` | `frontend/src/App.tsx:1530` | `onClick` → `setSearch("")` | — | — | — | Clears the filter | `search: ''` | none observed in code | frontend-only |
| 123 | Operator library | `算子库管理` / `服务器算子库` | `frontend/src/App.tsx:1535` | `onClick` → `setPluginsOpen('manage')` / `setAppSettings('servers')` | — | — | — | Opens the manage tab, or the Servers settings when a remote execution position is selected | `pluginsOpen: 'manage'` / `appSettings: 'servers'` | none observed in code | frontend-only |
| 124 | Operator library | `运行状态` | `frontend/src/App.tsx:1536` | `onClick` → `setStatusOpen(true)` → `<RuntimeStatusPanel/>` (`:1916`) | panel polls `api.pool`/`api.environments`/`api.version` (`RuntimeStatusPanel.tsx:513-537`) | `GET /api/pool` — `src/web/pool_api.py:22`; `GET /api/environments` — `src/web/environment_api.py:679`; `GET /api/version` — `src/web/api.py:143` | `pool` (`pool_api.py:23-51`); `list_environments` (`environment_api.py:680-682`); `version` (`api.py:143-146`) | Opens the runtime panel, which then polls every 3000 ms | `statusOpen: bool` | panel renders the last `ApiError.message` inline | verified |
| 125 | Canvas toolbar | `打开算子库` (`aria-label`) | `frontend/src/App.tsx:1570` | `onClick` → `setLibraryOpen(true)` | — | — | — | Opens the library drawer | `libraryOpen: true` | none observed in code | frontend-only |
| 126 | Canvas toolbar | `撤销` (`aria-label`) | `frontend/src/App.tsx:1580` | `onClick` → `undo` | — | — | — | Pops one undoable canvas transaction | graph revision -1 | disabled when the undo stack is empty | frontend-only |
| 127 | Canvas toolbar | `重做` (`aria-label`) | `frontend/src/App.tsx:1589` | `onClick` → `redo` | — | — | — | Re-applies a transaction | graph revision +1 | disabled when the redo stack is empty | frontend-only |
| 128 | Canvas toolbar | `自动排布` | `frontend/src/App.tsx:1599` | `onClick` → `commit(autoLayout(graphRef.current))` | — | — | — | Rewrites node positions as one undoable transaction | graph revision +1 | none observed in code | frontend-only |
| 129 | Canvas toolbar | `打开检查器` (`aria-label`) | `frontend/src/App.tsx:1616` | `onClick` → `inspectNode(selected)` | — | — | — | Opens `Inspector` for the selected node | `inspector: node` | disabled without a selection | frontend-only |
| 130 | Canvas toolbar | `执行设置` (`aria-label`) | `frontend/src/App.tsx:1625` | `onClick` → `setSettings(true)` → `ExecutionSettings` | — (row 171 issues the only request) | — | — | Opens the execution settings popover | `settings: bool` | none observed in code | frontend-only |
| 131 | Canvas | `添加输入数据` (empty canvas) | `frontend/src/App.tsx:1742` | `onClick` → `add()` | — | — | — | Adds the input-data node | graph nodes | none observed in code | frontend-only |
| 132 | Canvas | `缩小画布` (`aria-label`) | `frontend/src/App.tsx:1758` | `onClick` → `flow.zoomOut()` | — | — | — | Viewport zoom only; never persisted | viewport zoom | none observed in code | frontend-only |
| 133 | Canvas | `放大画布` (`aria-label`) | `frontend/src/App.tsx:1773` | `onClick` → `flow.zoomIn()` | — | — | — | Viewport zoom | viewport zoom | none observed in code | frontend-only |
| 134 | Canvas | `适配画布` (`aria-label`) | `frontend/src/App.tsx:1789` | `onClick` → `fit` | — | — | — | Fits all nodes into the viewport | viewport | none observed in code | frontend-only |
| 135 | Canvas context menu | Menu scrim | `frontend/src/App.tsx:1891` | `onMouseDown`/`onContextMenu` → `setContextMenu(null)` | — | — | — | Dismisses the menu | `contextMenu → null` | none observed in code | frontend-only |
| 136 | Canvas context menu | `打开路线的算子图` | `frontend/src/App.tsx:1897` | `onClick` → `openRoute(route)` (`:508-511`) | — | — | — | Expands the saved route into its operator subgraph | graph nodes | none observed in code | frontend-only |
| 137 | Canvas context menu | `恢复到算子库` | `frontend/src/App.tsx:1899` | `onClick` → `manageLibrary(key,'restore')` (`:545-553`) | `api.manageLibrary` (`api.ts:382`) | `POST /api/library/manage` — `src/web/api.py:269` | `manage_library` (`api.py:269-272`) | Clears the hidden flag; persists `library_state.json` | hidden list shrinks; catalog refetched | `404` unknown key; `422` unknown action | verified |
| 138 | Canvas context menu | `添加到画布` | `frontend/src/App.tsx:1900` | `onClick` → `add(key)` | — | — | — | Inserts the node | graph nodes | disabled while `busy` or when library-disabled | frontend-only |
| 139 | Canvas context menu | `启用算子` / `禁用算子` | `frontend/src/App.tsx:1901` | `onClick` → `manageLibrary(key,'enable' / 'disable')` | `api.manageLibrary` (`api.ts:382`) | `POST /api/library/manage` — `src/web/api.py:269` | `manage_library` (`api.py:269-272`) | Toggles the disabled flag and writes `library_state.json` | `libraryState.disabled` | `404`/`422` | verified |
| 140 | Canvas context menu | `从算子库删除` | `frontend/src/App.tsx:1903` | `onClick` → `manageLibrary(key,'delete')` | `api.manageLibrary` (`api.ts:382`) | `POST /api/library/manage` — `src/web/api.py:269` | `manage_library` (`api.py:269-272`) | Hides the entry from the library (restorable via row 137) | `libraryState.hidden` grows | `404`/`422`; `menu-danger` styling only, no confirm dialog | verified |
| 141 | Canvas context menu | `复制选区上下文` | `frontend/src/App.tsx:1906` | `onClick` → `copyAgentContext()` (`:458`) | — | — | — | Serialises the selection to the clipboard | clipboard | disabled without a selection | frontend-only |
| 142 | Canvas context menu | `复制节点` | `frontend/src/App.tsx:1908` | `onClick` → `copySelection()` (`:571`) | — | — | — | Writes nodes to the in-memory clipboard | clipboard buffer | disabled without a selection | frontend-only |
| 143 | Canvas context menu | `粘贴` | `frontend/src/App.tsx:1909` | `onClick` → `pasteSelection(false, flow.screenToFlowPosition(pos))` (`:580`) | — | — | — | Inserts clipboard nodes at the cursor | graph nodes + revision | disabled while `busy` | frontend-only |
| 144 | Canvas context menu | `复制副本` | `frontend/src/App.tsx:1910` | `onClick` → `pasteSelection(true)` | — | — | — | Duplicates the selection in place | graph nodes + revision | disabled without a selection or while `busy` | frontend-only |
| 145 | Canvas | `关闭提示` (toast, `aria-label`) | `frontend/src/App.tsx:1933` | `onClick` → `setToast(null)` | — | — | — | Dismisses the toast | `toast → null` | none observed in code | frontend-only |
| 146 | Canvas run dialog | History entry button | `frontend/src/CanvasPlanDialog.tsx:85` | `onClick` → selects the record | GET `/api/v1/canvas-plans/outcome?request_id=` (`CanvasPlanDialog.tsx:67`) | `operon/canvas_api.py:54` | `outcome` (`canvas_api.py:55-58`) | Reads a past run's outcome for display | dialog `outcome` | `403` without `context` capability | verified |
| 147 | Canvas run dialog | `输出目录（留空自动创建）` (input) | `frontend/src/CanvasPlanDialog.tsx:88` | `onChange` → `setOutput` | — (submitted as `output` by row 149) | — | — | Sets the export destination | `output` | none observed in code | frontend-only |
| 148 | Canvas run dialog | `取消准备` | `frontend/src/CanvasPlanDialog.tsx:89` | `onClick` → `cancelPreparation()` (`:73`) | POST `/api/v1/canvas-plans/cancel` (`CanvasPlanDialog.tsx:74`) | `operon/canvas_api.py:37` | `cancel` (`canvas_api.py:38-41`) | Cancels an in-flight prepare; no effect once `status === 'ready'` (`operon/canvas_plans.py:92`) | `preparing → cancelled` | `403` without `run` capability | verified |
| 149 | Canvas run dialog | `用原标识确认运行` / `导出独立运行包` | `frontend/src/CanvasPlanDialog.tsx:90` | `onClick` → `execute()` (`:51`) | POST `/api/v1/canvas-plans/execute` (`CanvasPlanDialog.tsx:51`) | `operon/canvas_api.py:42` | `execute` (`canvas_api.py:43-48`) | Submits the prepared plan as a real run/export on the chosen host; `canvas_plans.execute` refuses unless `status === 'ready'` (`operon/canvas_plans.py:281`) | `ready → running`; `busy` | `422` with `code` `portable_tool_required` (`operon/environment_store/closures.py:38`) or `multi_host_plan_required` (`operon/canvas_plans.py:253`), surfaced with the `执行计划` escape hatch | verified |
| 150 | Canvas run dialog | `运行环境设置` / `重新准备` | `frontend/src/CanvasPlanDialog.tsx:91` | `onClick` → `onEnvironment` / reset ids + `setRetry(true)` | — | — | — | Opens the runtime panel, or re-runs prepare | dialog state reset | none observed in code | frontend-only |
| 151 | Canvas run dialog | `执行计划` (escape hatch) | `frontend/src/CanvasPlanDialog.tsx:94` | `onClick` → `onAdvanced` when `prepared.code` ∈ `portable_tool_required`/`multi_host_plan_required` | — | — | — | Switches to the plan panel | dialogs swap | none observed in code | frontend-only |
| 152 | Canvas run dialog | `用原标识确认提交结果` | `frontend/src/CanvasPlanDialog.tsx:95` | `onClick` → `retryPending()` (`:77`) | POST `/api/v1/canvas-plans/execute` (`CanvasPlanDialog.tsx:79`) | `operon/canvas_api.py:42` | `execute` (`canvas_api.py:43-48`) | Re-submits the same `preparation_id` after a transport failure | `pending → submitted` | as row 149 | verified |
| 153 | Plan panel | Tab buttons `准备` / `运行记录` / `导出` | `frontend/src/PlanPanel.tsx:108` | `onClick` → `setTab(key)` | — | — | — | Client-side pane switch | `tab: 'prepare' / 'runs' / 'export'` | none observed in code | frontend-only |
| 154 | Plan panel | `重新读取记录` | `frontend/src/PlanPanel.tsx:114` | `onClick` → `action('reload', …)` → `planApi.state(signal)` | `planApi.state` (`planApi.ts:12`) | `GET /api/v1/plan-ui-state` — `operon/plan_ui_state.py:99` | `plan_ui_state` (`plan_ui_state.py:99-103`) | Re-reads the persisted plan records and selection state | `store` replaced; `busy` while in flight | `403` without `context` capability; `422` on a malformed state document | verified |
| 155 | Plan panel | `导入计划或清单` | `frontend/src/PlanPanel.tsx:118` | `onClick` → `fileInput.current?.click()` | — (file handled at `:165`) | — | — | Opens the hidden file input | none | none observed in code | frontend-only |
| 156 | Plan panel | `编译快照` | `frontend/src/PlanPanel.tsx:119` | `onClick` → `compile()` | `planApi.compile` (`planApi.ts:8`) | `POST /api/v1/plans/compile` — `operon/plan_api.py:60` | `compile_plan` (`plan_api.py:60-64`) | Compiles the current canvas/metadata into a run plan (read-only, no job) | `plan: null → RunPlan`; binding rows appear | `422` `ContractError` (handler at `plan_api.py:32`); `403` without `edit`/`run` scope | verified |
| 157 | Plan panel | `使用当前画布` | `frontend/src/PlanPanel.tsx:121` | `onClick` → clears `source`/`selected`/`plan` | — | — | — | Drops the imported plan and falls back to the live canvas | `source: null`, `plan: null` | none observed in code | frontend-only |
| 158 | Plan panel | `核对环境与输入` | `frontend/src/PlanPanel.tsx:126` | `onClick` → `inspectBindings()` | `planApi.bindingOptions` (`planApi.ts:9-11`) | `POST /api/v1/plans/binding-options` — `operon/plan_binding_options.py:83` | `binding_options` (`plan_binding_options.py:83-90`) | Resolves available environment generations and storage/input candidates for the compiled plan | `options` populated; rows for `环境`/`存储`/`输入` become selects | `422` `ContractError`; `403` without `context` | verified |
| 159 | Plan panel | `导入绑定清单` | `frontend/src/PlanPanel.tsx:127` | `onClick` → `bindingInput.current?.click()` | — (file handled at `:166`) | — | — | Opens the hidden binding-file input | none | none observed in code | frontend-only |
| 160 | Plan panel | Binding path inputs (`包根目录`, `环境存储` etc.) | `frontend/src/PlanPanel.tsx:130` | `onChange` → `setBinding` (also clears `options` and `environments`) | — (submitted by row 166) | — | — | Edits the binding payload sent to `POST /api/v1/plans` | `binding.*`; `options → null` | none observed in code | frontend-only |
| 161 | Plan panel | `已验证的环境版本` (select per environment) | `frontend/src/PlanPanel.tsx:132` | `onChange` → `setBinding(environments[name].generation_id)` | — | — | — | Pins a specific environment generation for the run | `binding.environments` | none observed in code | frontend-only |
| 162 | Plan panel | `存储` · {name} (input) | `frontend/src/PlanPanel.tsx:139` | `onChange` → `setBinding(storage[name])` | — | — | — | Maps a required storage slot to a path | `binding.storage` | none observed in code | frontend-only |
| 163 | Plan panel | `输入` · {name} / `文件相对路径` (input) | `frontend/src/PlanPanel.tsx:140` | `onChange` → `updateInput(name, value)` | — | — | — | Maps a required input to a file path | `binding.inputs[name].path` | none observed in code | frontend-only |
| 164 | Plan panel | `表示格式` (select) | `frontend/src/PlanPanel.tsx:141` | `onChange` → `setBinding(inputs[name].representation)` | — | — | — | Chooses `file`/other representation; resets `sha256` | `binding.inputs[name].representation` | none observed in code | frontend-only |
| 165 | Plan panel | `保存计划清单` | `frontend/src/PlanPanel.tsx:148` | `onClick` → `downloadText('execution-plan.json', …)` | — | — | — | Writes `{plan, binding}` to a local download; no request | file download | none observed in code | frontend-only |
| 166 | Plan panel | `提交此计划` | `frontend/src/PlanPanel.tsx:149` | `onClick` → `submit()` | `planApi.submit` (`planApi.ts:14`) | `POST /api/v1/plans` — `operon/plan_api.py:65` (status 202) | `submit_plan` (`plan_api.py:65-69`) | Persists the plan record and hands it to the engine; returns a `PlanReceipt` | `record.status: accepted → running`; `busy` | disabled while `locked`, `busy`, or `missing.length > 0`; `422` `ContractError`; `409` on duplicate `request_id` | verified |
| 167 | Plan panel | Plan history record | `frontend/src/PlanPanel.tsx:154` | `onClick` → `setSelected(request_id)` | — | — | — | Selects a stored record | `selected` | none observed in code | frontend-only |
| 168 | Plan panel | `用原标识确认提交` | `frontend/src/PlanPanel.tsx:160` | `onClick` → `submit(selectedRecord)` | `planApi.submit` (`planApi.ts:14`) | `POST /api/v1/plans` — `operon/plan_api.py:65` (202) | `submit_plan` (`plan_api.py:65-69`) | Re-submits a record that ended `accepted`/`rejected` using its original `request_id` | `record.status → running` | `422` `ContractError`; `409` duplicate `request_id` | verified |
| 169 | Plan panel | `归档` (record action) | `frontend/src/PlanPanel.tsx:156` | `onClick` -> `action('archive', ...)` -> `save()` (`:39-41`) | `planApi.saveState` -> `frontend/src/planApi.ts:9` | `POST /api/v1/plan-ui-state` | `operon/plan_ui_state.py:102-104` (`write_state`, `bridge.actor(request, 'edit')`) | Persists the plan history with the record removed | `records` | write rejection -> `action()` surfaces the error | verified |
| 170 | Plan panel | `导入计划或清单` (file input) | `frontend/src/PlanPanel.tsx:165` | `onChange` → `importFile()` (`:57-66`) | none — `parsePlanFile()` runs in the renderer | none | none | Sets `plan` / `binding` / `source` from the file | `plan`, `binding`, `source` | invalid JSON → local throw | frontend-only |
| 171 | Plan panel | `导入绑定清单` (file input) | `frontend/src/PlanPanel.tsx:166` | `onChange` → `action('binding-import', …)` | none — `JSON.parse` + `setBinding` | none | none | Replaces the binding form from the file | `binding` | missing keys → `执行绑定清单不完整。` | frontend-only |
| 172 | Execution settings | Execution target radio (`role="menuitemradio"`) | `frontend/src/ExecutionSettings.tsx:25-27` | `onClick` → `onSelect(target)` | — | — | — | Chooses the host the graph will run on | `execution.target` | disabled when `automatic` | frontend-only |
| 173 | Execution settings | `自动` | `frontend/src/ExecutionSettings.tsx:51-52` | `onClick` → `onChange({mode:'auto'})` | — | — | — | Lets the engine choose the host | `config.mode: 'auto'` | none observed in code | frontend-only |
| 174 | Execution settings | `手动` | `frontend/src/ExecutionSettings.tsx:53-54` | `onClick` → `onChange({mode:'manual'})` | — | — | — | Requires an explicit host | `config.mode: 'manual'` | none observed in code | frontend-only |
| 175 | Execution settings | `默认运行环境` (select) | `frontend/src/ExecutionSettings.tsx:57` | `onChange` → `onChange(target)` | — | — | — | Default environment key for nodes without an override | `config.default_target` | none observed in code | frontend-only |
| 176 | Execution settings | `并行任务上限` (number input) | `frontend/src/ExecutionSettings.tsx:65` | `onChange` → `onChange(parallel)` | — | — | — | Caps concurrent tasks; placeholder `按可用资源` means engine default | `config.parallel` | none observed in code | frontend-only |
| 177 | Execution settings | Preview/check button (`execution-preview-button`) | `frontend/src/ExecutionSettings.tsx:68` | `onClick` → `inspect()` (`:42-44`) | `api.executionPlan` (`api.ts:216`) | `POST /api/execution/plan` — `src/web/execution_api.py:45` | `execution_plan` (`execution_api.py:45-48`) | Asks the engine how the graph would be scheduled (hosts, queues, parallel slots) | `preview` rendered | `422` on an invalid graph; 500 handler | verified |
| 178 | Runs | Tab buttons `结果` / `运行日志` / `任务` / `运行记录` | `frontend/src/Results.tsx:286-291` | `onClick` → `onTab(key)` | — | — | — | Switches the dock pane | `tab` | none observed in code | frontend-only |
| 179 | Runs | `收起` / `展开` | `frontend/src/Results.tsx:316` | `onClick` → `onToggle` | — | — | — | Collapses the dock | `collapsed: bool` | none observed in code | frontend-only |
| 180 | Runs | History row name button | `frontend/src/Results.tsx:334` | `onClick` → `openJob(item.id,'results')` → `onJob` → `api.job(id)` (`App.tsx:1831`) | `api.job` (`api.ts:398`) | `GET /api/jobs/{key}` — `src/web/api.py:413` | `job_details` (`api.py:414-432`) | Loads one job's detail (steps, artifacts, console) into the pane | `job: null → detail` | `404` `{code:'unknown_job', message:'unknown job or resource operation: …'}` (`api.py:428-431`), shown as an empty pane | verified |
| 181 | Runs | `查看结果` / `查看进度` | `frontend/src/Results.tsx:354` | `onClick` → `openJob(id,'results')` | `api.job` (`api.ts:398`) | `GET /api/jobs/{key}` — `api.py:413` | `job_details` (`api.py:414-432`) | Same fetch as row 180, landing on the results tab | `tab: 'results'` | `404` unknown job | verified |
| 182 | Runs | `查看日志` | `frontend/src/Results.tsx:357` | `onClick` → `openJob(id,'logs')` | `api.job` (`api.ts:398`) | `GET /api/jobs/{key}` — `api.py:413` | `job_details` (`api.py:414-432`) | Same fetch, landing on the log tab | `tab: 'logs'` | `404` unknown job | verified |
| 183 | Runs | `载入画布` (history row) | `frontend/src/Results.tsx:359` | `onClick` → `api.job(item.id).then(onRestore)` (`:362-364`) | `api.job` (`api.ts:398`) | `GET /api/jobs/{key}` — `api.py:413` | `job_details` (`api.py:414-432`) | Fetches the job's stored graph and reopens it as a canvas document | new document page | `404` unknown job | verified |
| 184 | Runs | `完整进程日志` (link) | `frontend/src/Results.tsx:437` | plain `<a href>` → `api.url('/api/jobs/'+job.id+'/console')` | `api.url` (`api.ts:409`) | `GET /api/jobs/{key}/console` — `src/web/api.py:523` | `job_console` (`api.py:523-537`) | Streams the subprocess console log; no token header, relies on GET being unauthenticated | new tab | `404` when the job has no console file | verified |
| 185 | Runs | `查看运行日志` | `frontend/src/Results.tsx:460` | `onClick` → switches to the log tab | — | — | — | Pane switch only | `tab: 'logs'` | none observed in code | frontend-only |
| 186 | Runs | `查看所有任务` | `frontend/src/Results.tsx:471` | `onClick` → switches to the task tab | — | — | — | Pane switch only | `tab: 'tasks'` | none observed in code | frontend-only |
| 187 | Runs | Saved figure button | `frontend/src/Results.tsx:481` | `onClick` → `report(item.index, item.id)` (`:256-270`) | `api.step` (`api.ts:405`) | `GET /api/jobs/{id}/exports/{index}` — `src/web/api.py:506` | `job_export` (`api.py:506-512`) | Fetches one step's report; payloads over 4 MiB come back as `{'message':'步骤报告较大，请下载查看。'}` | `step` preview shown | `404` unknown job/index; 4 MiB truncation is a 200 response | verified |
| 188 | Runs | Artifact select | `frontend/src/Results.tsx:488` | `onChange` → `setSelected` | — | — | — | Selects which artifact's files/downloads are shown | `selected` | none observed in code | frontend-only |
| 189 | Runs | Step select | `frontend/src/Results.tsx:510` | `onChange` → `report(index)` | `api.step` (`api.ts:405`) | `GET /api/jobs/{id}/exports/{index}` — `api.py:506` | `job_export` (`api.py:506-512`) | Loads the selected step report | `step` | `404` | verified |
| 190 | Runs | `重试` (failed result) | `frontend/src/Results.tsx:525` | `onClick` → `report(step)` or `setReload(v => v+1)` | `api.job` (`api.ts:398`) / `api.step` (`api.ts:405`) | `GET /api/jobs/{key}` — `api.py:413`; `GET /api/jobs/{id}/exports/{index}` — `api.py:506` | `job_details` (`api.py:414-432`); `job_export` (`api.py:506-512`) | Re-fetches the result/step; it does **not** re-run the job (no POST) | `reload` counter increments | `404` | degraded |
| 191 | Runs | JSON download (link) | `frontend/src/Results.tsx:531` | plain `<a href>` → `/api/jobs/{id}/exports/{step}/download` | `api.url` (`api.ts:409`) | `GET /api/jobs/{key}/exports/{index}/download` — `src/web/api.py:513` | `job_export_download` (`api.py:513-517`) | Streams the step report JSON | new tab | `404` unknown job/index | verified |
| 192 | Runs | Artifact download (link) | `frontend/src/Results.tsx:559` | plain `<a href>` → `/api/jobs/{id}/artifacts/{selected}/download` | `api.url` (`api.ts:409`) | `GET /api/jobs/{key}/artifacts/{artifact_id}/download` — `src/web/api.py:495` | `artifact_download` (`api.py:495-500`) | Streams the artifact (`.files.json` bundle or `.npy`) | new tab | `404` unknown artifact | verified |
| 193 | Runs | Per-file link | `frontend/src/Results.tsx:570` | plain `<a href>` → `/api/jobs/{id}/artifacts/{selected}/files/{role}` | `api.url` (`api.ts:409`) | `GET /api/jobs/{key}/artifacts/{artifact_id}/files/{role}` — `src/web/api.py:501` | `artifact_file` (`api.py:501-505`) | Streams one role file out of the artifact bundle | new tab | `404` unknown artifact/role | verified |
| 194 | Tasks | Task row (`task-select`) | `frontend/src/TaskManager.tsx:30` | `onClick` → `onSelect(job.id)` → `openJob` → `api.job` (`App.tsx:1831`) | `api.job` (`api.ts:398`) | `GET /api/jobs/{key}` — `src/web/api.py:413` | `job_details` (`api.py:414-432`) | Loads the task's detail into the results dock | `selected task` | `404` unknown job | verified |
| 195 | Tasks | `日志` | `frontend/src/TaskManager.tsx:36` | `onClick` → `onLogs(job.id)` → `onJob` → `api.job` | `api.job` (`api.ts:398`) | `GET /api/jobs/{key}` — `api.py:413` | `job_details` (`api.py:414-432`) | Loads detail and switches to the log tab | `tab: 'logs'` | `404` | verified |
| 196 | Tasks | `停止任务` (icon) | `frontend/src/TaskManager.tsx:37` | `onClick` → `onCancel(job.id)` → `App.tsx:1815` → `stop(id)` → `api.cancel(id)` (`App.tsx:1121`) | `api.cancel` (`api.ts:399`) | `POST /api/jobs/{key}/cancel` — `src/web/api.py:433` | `cancel_job` (`api.py:433-436`) | Requests cancellation of the running job; remote jobs are routed to `RemoteManager.cancel` (`src/web/service.py:1854-1856`) | `running → cancelling → cancelled` | `404` unknown job; remote jobs raise `KeyError('找不到远程运行记录，请连接服务器刷新。')` from `RemoteManager.reference` (`src/web/remote_service.py:625`) → `404` | verified |
| 197 | Settings | `关闭设置` | `frontend/src/SettingsPage.tsx:29` | `onClick` → `onClose` | — | — | — | Closes the modal | `appSettings → null` | none observed in code | frontend-only |
| 198 | Settings | Section nav: `服务器` / `输出与查看器` / `外观` / `语言` | `frontend/src/SettingsPage.tsx:31` | `onClick` → `setSection(id)` (`:25`) | — | — | — | Switches the embedded settings section (`RemotePanel` / `ViewerSettings` / `AppearanceSettings` / `LanguageSettings`, `:33-36`) | `section: 'servers' / 'viewers' / 'appearance' / 'language'` | none observed in code | frontend-only |
| 199 | Plugin panel | Tab `算子库管理` | `frontend/src/PluginPanel.tsx:127` | `onClick` → `setTab('manage')` | — | — | — | Switches to the manage tab, which then loads `api.plugins()` and `api.libraries()` (`:28`, `:39`) | `tab: 'manage'` | load errors render in the panel error line | frontend-only |
| 200 | Plugin panel | Tab `添加算子` | `frontend/src/PluginPanel.tsx:128` | `onClick` → `setTab('add')` | — | — | — | Switches to the add tab | `tab: 'add'` | none observed in code | frontend-only |
| 201 | Plugin panel | `刷新算子库` | `frontend/src/PluginPanel.tsx:144` | `onClick` → `operate(api.refreshPlugins)` | `api.refreshPlugins` (`api.ts:266`) | `POST /api/plugins/refresh` — `src/web/plugin_api.py:108` | `refresh_plugins` (`plugin_api.py:108-114`) | Rescans plugins/operators; the panel also polls `api.plugins()` every 1000 ms (`:34`) | `pending: bool`; button shows a spinner | errors caught into `setError(e.message)` | verified |
| 202 | Plugin panel | `修复依赖` / `修复中…` | `frontend/src/PluginPanel.tsx:145` | `onClick` → `operate(api.repairDependencies)` | `api.repairDependencies` (`api.ts:267`) | `POST /api/plugins/dependencies` — `src/web/plugin_api.py:84` | `repair_dependencies` (`plugin_api.py:84-87`) | Installs missing plugin dependencies and any isolated environment the libraries declare | disabled while `state.dependencies?.running` | errors into the panel error line | verified |
| 203 | Plugin panel | `删除算子库` | `frontend/src/PluginPanel.tsx:158` | `onClick` → `removeLibrary(record)` (`:63`) | `api.deleteLibrary` (`api.ts:299`) | `DELETE /api/libraries/{name}` — `src/web/library_api.py:109` | `delete_library` (`library_api.py:109-121`) | Uninstalls the library and removes its files | library row disappears; toast `已删除算子库 {name}。` | `404` unknown library; `409` while a library operation runs | verified |
| 204 | Plugin panel | `完成` | `frontend/src/PluginPanel.tsx:172` | `onClick` → `onClose` | — | — | — | Closes the panel | `pluginsOpen → null` | none observed in code | frontend-only |
| 217 | Plugin panel | Hidden file input `算子库包` (`.operon-library.zip` / `.whl`) | `frontend/src/PluginPanel.tsx:131-137` | `onChange` -> `operate(bundle ? () => api.installLibrary(selected) : () => api.installPlugin(selected))` (`:136`, with `bundle = isLibraryBundleFile(selected.name)` at `:135`) | `api.installLibrary` (`api.ts:286`) / `api.installPlugin` (`api.ts:272`) | `POST /api/libraries/install` - `src/web/library_api.py:84`; `POST /api/plugins/install?filename=` - `src/web/plugin_api.py:133` | `install_library_route` (`src/web/library_api.py:85`) / `install` (`src/web/plugin_api.py:134`) | Uploads the archive, installs it as an operator library or a plugin, then reloads the catalog | `pending` on the panel (`operate`) | `422` `请选择 .whl 或 .operon-library.zip 算子库包。` (`src/web/plugin_api.py:139`); `409` while another plugin operation is active (`check_idle`, `:136`) | verified |
| 205 | File picker (storage) | `关闭文件选择` (`aria-label`) | `frontend/src/StorageFilePicker.tsx:101` | `onClick` → `onClose` | — | — | — | Closes the picker | picker unmounted | none observed in code | frontend-only |
| 206 | File picker (storage) | `文件位置` (select) | `frontend/src/StorageFilePicker.tsx:103` | `onChange` → `setStorage` then `browse` | `api.storageRoots` (`api.ts:254`) / `api.browseStorage` (`api.ts:255`) | `GET /api/v1/storage/roots` — `operon/storage_api.py:83`; `POST /api/v1/storage/browse` — `storage_api.py:89` | `storage_roots` (`storage_api.py:83-88`); `storage_browse` (`storage_api.py:90-92`) | Lists configured storage roots, then browses the chosen one | `storage`, `page` | `409`/`422` storage errors; `busy` disables the select | verified |
| 207 | File picker (storage) | `上级目录` (`aria-label`) | `frontend/src/StorageFilePicker.tsx:108-109` | `onClick` → `browse(storage, storageParent(location), hidden)` | `api.browseStorage` (`api.ts:255`) | `POST /api/v1/storage/browse` — `operon/storage_api.py:89` | `storage_browse` (`storage_api.py:90-92`) | Moves up one directory inside the storage root | `location` | `409`/`422` | verified |
| 208 | File picker (storage) | `相对目录` (input) | `frontend/src/StorageFilePicker.tsx:110` | `onChange` → `setPath` | — (submitted by row 209) | — | — | Edits the relative path to open | `path` | none observed in code | frontend-only |
| 209 | File picker (storage) | `打开目录` (submit, `aria-label`) | `frontend/src/StorageFilePicker.tsx:111` | form submit (`:107`) → `browse(storage, path, hidden)` | `api.browseStorage` (`api.ts:255`) | `POST /api/v1/storage/browse` — `storage_api.py:89` | `storage_browse` (`storage_api.py:90-92`) | Opens the typed relative path | `location` | `409`/`422` | verified |
| 210 | File picker (storage) | `重新加载` (`aria-label`) | `frontend/src/StorageFilePicker.tsx:112-113` | `onClick` → `browse(storage, location, hidden)` | `api.browseStorage` (`api.ts:255`) | `POST /api/v1/storage/browse` — `storage_api.py:89` | `storage_browse` (`storage_api.py:90-92`) | Refreshes the current listing | `page` | `409`/`422` | verified |
| 211 | File picker (storage) | Entry row (`role="option"`) | `frontend/src/StorageFilePicker.tsx:117-121` | `onClick` → directory: `browse`; file: `setSelected` | `api.browseStorage` (`api.ts:255`) on directories | `POST /api/v1/storage/browse` — `storage_api.py:89` | `storage_browse` (`storage_api.py:90-92`) | Descends into a directory or selects a file | `selected` | `409`/`422` | verified |
| 212 | File picker (storage) | `下一页` | `frontend/src/StorageFilePicker.tsx:134` | `onClick` → `browse(…, page.next_cursor)` | `api.browseStorage` (`api.ts:255`) | `POST /api/v1/storage/browse` — `storage_api.py:89` | `storage_browse` (`storage_api.py:90-92`) | Pages through a large directory | `page.next_cursor` | `409`/`422` | verified |
| 213 | File picker (storage) | Hidden-files checkbox | `frontend/src/StorageFilePicker.tsx:140` | `onChange` → `setHidden` + `browse` | `api.browseStorage` (`api.ts:255`) | `POST /api/v1/storage/browse` — `storage_api.py:89` | `storage_browse` (`storage_api.py:90-92`) | Includes/excludes dotfiles | `hidden: bool` | `409`/`422` | verified |
| 214 | File picker (storage) | `预览` | `frontend/src/StorageFilePicker.tsx:143` | `onClick` → `inspect(selected)` (`:88-92`) | `api.statStorage` (`api.ts:257`) then `api.previewStorage` (`api.ts:259`) | `POST /api/v1/storage/stat` — `storage_api.py:93`; `POST /api/v1/storage/preview` — `storage_api.py:97` | `storage_stat` (`storage_api.py:93-96`); `storage_preview` (`storage_api.py:97-100`) | Stats the file, then reads a bounded preview | `preview` | `409`/`422` on unreadable files | verified |
| 215 | File picker (storage) | `选择文件` | `frontend/src/StorageFilePicker.tsx:144` | `onClick` → `inspect(selected, true)` → `onSelect` | `api.statStorage` (`api.ts:257`) / `api.previewStorage` (`api.ts:259`) | as row 214 | as row 214 | Confirms the selection and returns the storage reference to the caller | picker closes; caller receives the reference | `409`/`422` | verified |
| 216 | File picker (storage) | Session cleanup on unmount | `frontend/src/StorageFilePicker.tsx:59-74` | `useEffect` cleanup → `closeStorageBrowse(session)` | `api.closeStorageBrowse` (`api.ts:262`) | `POST /api/v1/storage/browse/close` — `operon/storage_api.py:108` | `storage_close` (`storage_api.py:108-114`) | Releases the browse session (server-side handle) | session closed | errors swallowed (`.catch(() => {})`) | verified |

## Backend endpoints

Reverse index of every route registered by `src/web/*.py`, `operon/control_api.py` and `operon/bridge.py`, plus the engine modules those three mount. `Callers` lists the control numbers from the table above; `—` means no frontend control in this audit reaches the route (CLI, MCP or internal callers only).

**Auth legend.** `token` = the `x-studio-token` header is required by the `local_boundary` middleware (`src/web/api.py:98-100`) because the route is a non-GET under `/api/`; `none` = no token (every GET under `/api/`); `token|agent` = the handler calls `Bridge.actor()` (`operon/bridge.py:51-65`), which accepts the studio token or a scoped agent bearer token; `agent` = the route lives under `/api/agent/`, which the middleware excludes and the bridge authenticates itself.

### `src/web/api.py`

| Method Path | Implementation | Callers | Auth |
| --- | --- | --- | --- |
| `GET /health` | `src/web/api.py:138` | — | none |
| `GET /ready` | `src/web/api.py:139` | — | none |
| `GET /api/version` | `src/web/api.py:143` | 124 | none |
| `GET /api/bootstrap` | `src/web/api.py:147` | 85 | none |
| `GET /api/workspace` | `src/web/api.py:166` | — | none |
| `POST /api/workspace` | `src/web/api.py:170` | — | token |
| `GET /api/workflows` | `src/web/api.py:175` | 90 | none |
| `POST /api/workflows/prepare` | `src/web/api.py:179` | — (SaveWorkflowDialog uses `api.prepareWorkflow`, `RouteDialogs.tsx:73`) | token |
| `POST /api/workflows/export` | `src/web/api.py:183` | 94 | token |
| `POST /api/workflows/export-yaml` | `src/web/api.py:188` | 96 | token |
| `POST /api/workflows/import` | `src/web/api.py:195` | 108, 109 | token |
| `POST /api/routes/import-archive` | `src/web/api.py:208` | 109 | token |
| `POST /api/workflows/save` | `src/web/api.py:241` | 91, 109 | token |
| `GET /api/workflows/{key}` | `src/web/api.py:253` | 90 | none |
| `GET /api/routes` | `src/web/api.py:257` | — (catalog bootstrap path) | none |
| `POST /api/routes/register` | `src/web/api.py:261` | — (`api.registerRoutes`, `RouteDialogs.tsx:49`) | token |
| `GET /api/library/state` | `src/web/api.py:265` | — | none |
| `POST /api/library/manage` | `src/web/api.py:269` | 137, 139, 140 | token |
| `GET /api/operators` | `src/web/api.py:273` | 113 | none |
| `POST /api/validate` | `src/web/api.py:279` | 103 | token |
| `POST /api/prepare-environment` | `src/web/api.py:283` | — | token |
| `POST /api/check-environment` | `src/web/api.py:287` | — (`api.checkEnvironment`) | token |
| `POST /api/contracts` | `src/web/api.py:291` | — (`RouteDialogs.tsx:73`) | token |
| `POST /api/export` | `src/web/api.py:295` | 95 | token |
| `POST /api/import` | `src/web/api.py:307` | 108 | token |
| `POST /api/assets/batches` | `src/web/api.py:337` | — (`api.uploadFiles`) | token |
| `POST /api/assets/batches/{key}/complete` | `src/web/api.py:343` | — | token |
| `POST /api/assets/batches/{key}/cancel` | `src/web/api.py:348` | — | token |
| `POST /api/assets` | `src/web/api.py:353` | — | token |
| `GET /api/jobs` | `src/web/api.py:385` | — (history dock is fed by `api.history`) | none |
| `POST /api/jobs` | `src/web/api.py:409` (202) | **none — `api.run` is never called** | token |
| `GET /api/jobs/{key}` | `src/web/api.py:413` | 180, 181, 182, 183, 190, 194, 195 | none |
| `POST /api/jobs/{key}/cancel` | `src/web/api.py:433` | 196 | token |
| `GET /api/jobs/{key}/events` | `src/web/api.py:437` | — | none |
| `GET /api/jobs/{key}/artifacts/{artifact_id}/preview` | `src/web/api.py:491` | — (`api.preview`) | none |
| `GET /api/jobs/{key}/artifacts/{artifact_id}/download` | `src/web/api.py:495` | 192 | none |
| `GET /api/jobs/{key}/artifacts/{artifact_id}/files/{role}` | `src/web/api.py:501` | 193 | none |
| `GET /api/jobs/{key}/exports/{index}` | `src/web/api.py:506` | 187, 189, 190 | none |
| `GET /api/jobs/{key}/exports/{index}/download` | `src/web/api.py:513` | 191 | none |
| `GET /api/jobs/{key}/exports/{index}/figure` | `src/web/api.py:518` | — | none |
| `GET /api/jobs/{key}/console` | `src/web/api.py:523` | 184 | none |

### `src/web/environment_api.py`

| Method Path | Implementation | Callers | Auth |
| --- | --- | --- | --- |
| `GET /api/environments` | `src/web/environment_api.py:679` | 2, 124 | none |
| `POST /api/environments/{name}/dependencies/download` | `src/web/environment_api.py:683` | 19 | token |
| `POST /api/v1/environments/{name}/dependencies/download` | `src/web/environment_api.py:684` | — (engine alias) | token\|agent |
| `POST /api/environments/prepare` | `src/web/environment_api.py:698` | 3, 5, 18 | token |
| `POST /api/environments/{name}/retry` | `src/web/environment_api.py:727` | 6 | token |
| `POST /api/v1/environments/{name}/retry` | `src/web/environment_api.py:728` | — | token\|agent |
| `POST /api/environments/{name}/repair` | `src/web/environment_api.py:736` | — (no frontend caller; the UI reuses `retry`) | token |
| `POST /api/v1/environments/{name}/repair` | `src/web/environment_api.py:737` | — | token\|agent |
| `POST /api/environments/{name}/cancel` | `src/web/environment_api.py:745` | 8, 13 | token |
| `POST /api/v1/environments/{name}/cancel` | `src/web/environment_api.py:746` | — | token\|agent |
| `GET /api/environments/{name}/log` | `src/web/environment_api.py:805` | 7, 14 | none |
| `GET /api/v1/environments/{name}/log` | `src/web/environment_api.py:806` | — | token\|agent |

### `src/web/remote_api.py`

| Method Path | Implementation | Callers | Auth |
| --- | --- | --- | --- |
| `GET /api/remote` | `src/web/remote_api.py:23` | — (`api.remoteStatus`) | none |
| `GET /api/remote/summary` | `src/web/remote_api.py:27` | — | none |
| `POST /api/remote/profiles` | `src/web/remote_api.py:31` | 56, 58 | token |
| `POST /api/remote/{key}/connect` | `src/web/remote_api.py:35` | 58 | token |
| `POST /api/remote/{key}/install` | `src/web/remote_api.py:39` | 56, 73 | token |
| `POST /api/remote/{key}/refresh` | `src/web/remote_api.py:47` | 59 | token |
| `GET /api/remote/{key}/build` | `src/web/remote_api.py:54` | — | none |
| `GET /api/remote/{key}/setup` | `src/web/remote_api.py:58` | 56 (poll) | none |
| `POST /api/remote/{key}/library/check` | `src/web/remote_api.py:62` | 69 | token |
| `POST /api/remote/{key}/library/install` | `src/web/remote_api.py:66` | — (`api.installRemoteLibrary`) | token |
| `POST /api/remote/{key}/library/sync` | `src/web/remote_api.py:70` | 71 | token |
| `GET /api/remote/{key}/library/plan` | `src/web/remote_api.py:74` | 70 | none |
| `GET /api/remote/{key}/library/status` | `src/web/remote_api.py:78` | 71 (poll) | none |
| `GET /api/remote/{key}/environments` | `src/web/remote_api.py:82` | 1, 25 | none |
| `POST /api/remote/{key}/environments/prepare` | `src/web/remote_api.py:86` | 9, 26 | token |
| `POST /api/remote/{key}/environments/{name}/dependencies/download` | `src/web/remote_api.py:91` | 20 | token |
| `POST /api/remote/{key}/environments/{name}/cancel` | `src/web/remote_api.py:95` | 12, 13 | token |
| `GET /api/remote/{key}/environments/{name}/log` | `src/web/remote_api.py:99` | 11, 14 | none |
| `POST /api/remote/{key}/environments/{name}/retry` | `src/web/remote_api.py:100` | 10 | token |
| `GET /api/remote/{key}/resources` | `src/web/remote_api.py:107` | 28 | none |
| `POST /api/remote/{key}/resources/{name}/link` | `src/web/remote_api.py:111` | 36 | token |
| `POST /api/remote/{key}/resources/{name}/download` | `src/web/remote_api.py:119` | 29, 31 | token |
| `DELETE /api/remote/{key}/resources/{name}/link` | `src/web/remote_api.py:128` | 30 | token |
| `GET /api/remote/{key}/pool` | `src/web/remote_api.py:132` | — | none |
| `POST /api/remote/{key}/pool/stop` | `src/web/remote_api.py:136` | 24 | token |
| `POST /api/remote/{key}/trust` | `src/web/remote_api.py:140` | 57 | token |
| `POST /api/remote/{key}/disconnect` | `src/web/remote_api.py:145` | 60, 61 | token |
| `POST /api/remote/{key}/remove` | `src/web/remote_api.py:150` | 62 | token |
| `POST /api/remote/{key}/browse` | `src/web/remote_api.py:155` | 34, 63-67 | token |
| `POST /api/remote/{key}/source` | `src/web/remote_api.py:159` | 68 | token |

### `src/web/resource_api.py`

| Method Path | Implementation | Callers | Auth |
| --- | --- | --- | --- |
| `POST /api/browse` | `src/web/resource_api.py:885` | 34, 37, 38, 39 | token |
| `GET /api/resources` | `src/web/resource_api.py:893` | 28 | none |
| `POST /api/resources/{name}/download` | `src/web/resource_api.py:900` | 29, 31 | token |
| `POST /api/resources/{name}/link` | `src/web/resource_api.py:911` | 36 | token |
| `DELETE /api/resources/{name}/link` | `src/web/resource_api.py:925` | 30 | token |
| `POST /api/resources/{name}/cancel` | `src/web/resource_api.py:936` | — (no frontend caller; resource jobs are not exposed in the panel) | token |
| `GET /api/resources/operations/{job_id}` | `src/web/resource_api.py:943` | — | none |
| `GET /api/resources/{name}/log` | `src/web/resource_api.py:950` | — | none |

### `src/web/pool_api.py`, `src/web/execution_api.py`, `src/web/preferences.py`

| Method Path | Implementation | Callers | Auth |
| --- | --- | --- | --- |
| `GET /api/pool` | `src/web/pool_api.py:22` | 22, 124 | none |
| `POST /api/pool/stop` | `src/web/pool_api.py:52` | 22, 23 | token |
| `POST /api/execution/plan` | `src/web/execution_api.py:45` | 177 | token |
| `GET /api/execution/resources` | `src/web/execution_api.py:49` | — (`api.executionResources`) | none |
| `POST /api/assets/reference` | `src/web/execution_api.py:53` | — (`api.uploadReference`) | token |
| `GET /api/preferences` | `src/web/preferences.py:30` | — | none |
| `POST /api/preferences` | `src/web/preferences.py:34` | — (`api.savePreferences`) | token |

### `src/web/plugin_api.py`

| Method Path | Implementation | Callers | Auth |
| --- | --- | --- | --- |
| `POST /api/plugins/dependencies` | `src/web/plugin_api.py:84` | 202 | token |
| `GET /api/plugins` | `src/web/plugin_api.py:88` | 199 | none |
| `POST /api/plugins/declarations` | `src/web/plugin_api.py:92` | — | token |
| `GET /api/plugins/operations/{key}` | `src/web/plugin_api.py:102` | 113 | none |
| `POST /api/plugins/refresh` | `src/web/plugin_api.py:108` | 113, 201 | token |
| `POST /api/plugins/open-folder` | `src/web/plugin_api.py:115` | — (`api.openPluginFolder`) | token |
| `POST /api/plugins/install` | `src/web/plugin_api.py:133` | — (`api.installPlugin`) | token |
| `POST /api/plugins/remove` | `src/web/plugin_api.py:167` | — (`api.removePlugin`) | token |
| `POST /api/plugins/manage` | `src/web/plugin_api.py:177` | — (`api.managePlugin`) | token |

### `src/web/library_api.py`, `src/web/script_api.py`

| Method Path | Implementation | Callers | Auth |
| --- | --- | --- | --- |
| `GET /api/libraries` | `src/web/library_api.py:79` | 199 | none |
| `POST /api/libraries/install` | `src/web/library_api.py:84` | — (`PluginPanel.tsx:136`) | token |
| `DELETE /api/libraries/{name}` | `src/web/library_api.py:109` | 203 | token |
| `GET /api/route-collections` | `src/web/library_api.py:122` | — | none |
| `DELETE /api/route-collections/{slug}` | `src/web/library_api.py:127` | — | token |
| `POST /api/routes/import-collection` | `src/web/library_api.py:140` | — (`api.importRouteCollection`) | token |
| `POST /api/scripts/inspect` | `src/web/script_api.py:64` | — | token |
| `POST /api/scripts/extract` | `src/web/script_api.py:82` | — | token |
| `GET /api/operators/{identifier}/source` | `src/web/script_api.py:90` | — | none |
| `POST /api/scripts/publish` | `src/web/script_api.py:94` | — | token |

### `operon/viewer_api.py`, `operon/storage_api.py`, `operon/canvas_api.py`

| Method Path | Implementation | Callers | Auth |
| --- | --- | --- | --- |
| `GET /api/v1/viewers` | `operon/viewer_api.py:31` | 77 | token\|agent |
| `POST /api/v1/viewers/default` | `operon/viewer_api.py:36` | 80, 82 | token\|agent |
| `POST /api/v1/viewers/{viewer}/configure` | `operon/viewer_api.py:41` | 75, 76 | token\|agent |
| `GET /api/v1/jobs/{job}/artifacts/{artifact}/viewers` | `operon/viewer_api.py:46` | — (`api.artifactViewers`) | token\|agent |
| `POST /api/v1/jobs/{job}/artifacts/{artifact}/prepare-viewer` | `operon/viewer_api.py:51` | — (`api.prepareViewer`) | token\|agent |
| `POST /api/v1/jobs/{job}/artifacts/{artifact}/open-viewer` | `operon/viewer_api.py:56` | — (`api.openViewer`) | token\|agent |
| `GET /api/v1/storage/roots` | `operon/storage_api.py:83` | 46, 206 | token\|agent |
| `POST /api/v1/storage/browse` | `operon/storage_api.py:89` | 206-213 | token\|agent |
| `POST /api/v1/storage/stat` | `operon/storage_api.py:93` | 214, 215 | token\|agent |
| `POST /api/v1/storage/preview` | `operon/storage_api.py:97` | 214, 215 | token\|agent |
| `POST /api/v1/storage/browse/cancel` | `operon/storage_api.py:101` | — | token\|agent |
| `POST /api/v1/storage/browse/close` | `operon/storage_api.py:108` | 216 | token\|agent |
| `GET /api/v1/storage/status` | `operon/storage_api.py:115` | — | token\|agent |
| `POST /api/v1/canvas-plans/prepare` | `operon/canvas_api.py:25` | 107, 149 (prepare step) | token\|agent |
| `GET /api/v1/canvas-plans/status` | `operon/canvas_api.py:32` | 149 (poll) | token\|agent |
| `POST /api/v1/canvas-plans/cancel` | `operon/canvas_api.py:37` | 148 | token\|agent |
| `POST /api/v1/canvas-plans/execute` | `operon/canvas_api.py:42` | 149, 152 | token\|agent |
| `GET /api/v1/canvas-plans/history` | `operon/canvas_api.py:49` | 106 | token\|agent |
| `GET /api/v1/canvas-plans/outcome` | `operon/canvas_api.py:54` | 146 | token\|agent |

### `operon/plan_api.py`, `operon/plan_ui_state.py`, `operon/plan_binding_options.py`

| Method Path | Implementation | Callers | Auth |
| --- | --- | --- | --- |
| `POST /api/v1/plans/compile` | `operon/plan_api.py:60` | 156 | token\|agent |
| `POST /api/v1/plans` | `operon/plan_api.py:65` (202) | 166, 168 | token\|agent |
| `GET /api/v1/plans/{run_id}` | `operon/plan_api.py:70` | — (`planApi.details`) | token\|agent |
| `POST /api/v1/plans/{run_id}/cancel` | `operon/plan_api.py:75` | — (`planApi.cancel`, no control calls it) | token\|agent |
| `GET /api/v1/plans/{run_id}/events` | `operon/plan_api.py:88` | — | token\|agent |
| `GET /api/v1/plans/{run_id}/attempts` | `operon/plan_api.py:95` | — | token\|agent |
| `GET /api/v1/plans/{run_id}/artifacts` | `operon/plan_api.py:103` | — | token\|agent |
| `GET /api/v1/plans/{run_id}/logs` | `operon/plan_api.py:111` | — | token\|agent |
| `GET /api/v1/plans/{run_id}/artifacts/{artifact_id}/files` | `operon/plan_api.py:120` | — | token\|agent |
| `GET /api/v1/plans/{run_id}/files/{file_id}/preview` | `operon/plan_api.py:128` | — | token\|agent |
| `GET /api/v1/plans/{run_id}/files/{file_id}/open` | `operon/plan_api.py:137` | — | token\|agent |
| `POST /api/v1/plan-exports` | `operon/plan_api.py:153` (202) | — (`planApi.export`) | token\|agent |
| `GET /api/v1/plan-exports/lookup` | `operon/plan_api.py:158` | — | token\|agent |
| `GET /api/v1/plan-exports/{export_id}` | `operon/plan_api.py:163` | — | token\|agent |
| `POST /api/v1/plan-exports/{export_id}/cancel` | `operon/plan_api.py:168` | — | token\|agent |
| `GET /api/v1/plan-ui-state` | `operon/plan_ui_state.py:99` | 154 | token\|agent |
| `POST /api/v1/plan-ui-state` | `operon/plan_ui_state.py:104` | — (`planApi.saveState`) | token\|agent |
| `POST /api/v1/plans/binding-options` | `operon/plan_binding_options.py:83` | 158 | token\|agent |

### `operon/control_api.py`

| Method Path | Implementation | Callers | Auth |
| --- | --- | --- | --- |
| `GET /api/v1/capabilities` | `operon/control_api.py:128` | — | token\|agent |
| `POST /api/v1/workflows/prepare-environment` | `operon/control_api.py:140` | — | token\|agent |
| `POST /api/v1/workflows/check-environment` | `operon/control_api.py:145` | — | token\|agent |
| `GET /api/v1/environment` | `operon/control_api.py:150` | — | token\|agent |
| `GET /api/v1/environments` | `operon/control_api.py:155` | — | token\|agent |
| `POST /api/v1/environments/prepare` | `operon/control_api.py:160` | — | token\|agent |
| `GET /api/v1/large-resources` | `operon/control_api.py:166` | — | token\|agent |
| `POST /api/v1/large-resources/{name}/download` | `operon/control_api.py:175` | — | token\|agent |
| `POST /api/v1/large-resources/{name}/link` | `operon/control_api.py:189` | — | token\|agent |
| `DELETE /api/v1/large-resources/{name}/link` | `operon/control_api.py:205` | — | token\|agent |
| `POST /api/v1/large-resources/{name}/cancel` | `operon/control_api.py:218` | — | token\|agent |
| `GET /api/v1/large-resources/operations/{job_id}` | `operon/control_api.py:227` | — | token\|agent |
| `GET /api/v1/large-resources/{name}/log` | `operon/control_api.py:236` | — | token\|agent |
| `GET /api/v1/libraries` | `operon/control_api.py:245` | — | token\|agent |
| `POST /api/v1/libraries/install` | `operon/control_api.py:251` | — | token\|agent |
| `DELETE /api/v1/libraries/{name}` | `operon/control_api.py:262` | — | token\|agent |
| `POST /api/v1/routes/import-collection` | `operon/control_api.py:273` | — | token\|agent |
| `POST /api/v1/tasks` | `operon/control_api.py:282` | — | token\|agent |
| `POST /api/v1/workspace/files` | `operon/control_api.py:287` | — | token\|agent |
| `POST /api/v1/workspace/files/binary` | `operon/control_api.py:292` | — | token\|agent |
| `GET /api/v1/guides` | `operon/control_api.py:301` | — | token\|agent |
| `GET /api/v1/guides/{topic}` | `operon/control_api.py:307` | — | token\|agent |
| `GET /api/v1/openapi.json` | `operon/control_api.py:313` | — | token\|agent |
| `GET /api/v1/workflows` | `operon/control_api.py:323` | — | token\|agent |
| `POST /api/v1/workflows/prepare` | `operon/control_api.py:328` | — | token\|agent |
| `POST /api/v1/workflows/validate` | `operon/control_api.py:333` | — | token\|agent |
| `POST /api/v1/workflows/export` | `operon/control_api.py:338` | — | token\|agent |
| `POST /api/v1/workflows` | `operon/control_api.py:344` | — | token\|agent |
| `GET /api/v1/workflows/{key}` | `operon/control_api.py:350` | — | token\|agent |
| `POST /api/v1/jobs` | `operon/control_api.py:355` (202) | — | token\|agent |
| `GET /api/v1/jobs` | `operon/control_api.py:360` | — | token\|agent |
| `GET /api/v1/jobs/{key}` | `operon/control_api.py:365` | — | token\|agent |
| `POST /api/v1/jobs/{key}/cancel` | `operon/control_api.py:377` | — | token\|agent |
| `GET /api/v1/jobs/{key}/logs` | `operon/control_api.py:387` | — | token\|agent |
| `GET /api/v1/jobs/{key}/parameters` | `operon/control_api.py:400` | — | token\|agent |
| `GET /api/v1/jobs/{key}/artifacts` | `operon/control_api.py:416` | — | token\|agent |
| `GET /api/v1/jobs/{key}/artifacts/{artifact_id}` | `operon/control_api.py:421` | — | token\|agent |
| `GET /api/v1/jobs/{key}/artifacts/{artifact_id}/preview` | `operon/control_api.py:426` | — | token\|agent |
| `GET /api/v1/jobs/{key}/artifacts/{artifact_id}/table` | `operon/control_api.py:431` | — | token\|agent |
| `GET /api/v1/jobs/{key}/artifacts/{artifact_id}/file` | `operon/control_api.py:439` | — | token\|agent |
| `GET /api/v1/jobs/{key}/results` | `operon/control_api.py:445` | — | token\|agent |
| `GET /api/v1/jobs/{key}/results/file` | `operon/control_api.py:455` | — | token\|agent |
| `GET /api/v1/jobs/{key}/reports/{index}` | `operon/control_api.py:461` | — | token\|agent |
| `GET /api/v1/jobs/{key}/reports/{index}/figure` | `operon/control_api.py:466` | — | token\|agent |
| `GET /api/v1/operators` | `operon/control_api.py:471` | — | token\|agent |
| `POST /api/v1/operators/describe` | `operon/control_api.py:477` | — | token\|agent |
| `GET /api/v1/resources` | `operon/control_api.py:482` | — | token\|agent |
| `GET /api/v1/engine` | `operon/control_api.py:487` | — | token\|agent |
| `GET /api/v1/engine/events` | `operon/control_api.py:492` | — | token\|agent |
| `GET /api/v1/remotes` | `operon/control_api.py:497` | — | token\|agent |
| `POST /api/v1/remotes` | `operon/control_api.py:502` | — | token\|agent |
| `POST /api/v1/remotes/{key}/connect` | `operon/control_api.py:507` | — | token\|agent |
| `POST /api/v1/remotes/{key}/trust` | `operon/control_api.py:512` | — | token\|agent |
| `GET /api/v1/preferences` | `operon/control_api.py:529` | — | token\|agent |
| `POST /api/v1/preferences` | `operon/control_api.py:535` | — | token\|agent |
| `GET /api/v1/workspace` | `operon/control_api.py:544` | — | token\|agent |
| `POST /api/v1/workspace` | `operon/control_api.py:549` | — | token\|agent |
| `GET /api/v1/version` | `operon/control_api.py:556` | — | token\|agent |
| `GET /api/v1/routes` | `operon/control_api.py:562` | — | token\|agent |
| `POST /api/v1/routes/register` | `operon/control_api.py:567` | — | token\|agent |
| `GET /api/v1/library/state` | `operon/control_api.py:573` | — | token\|agent |
| `POST /api/v1/library/manage` | `operon/control_api.py:578` | — | token\|agent |
| `GET /api/v1/route-collections` | `operon/control_api.py:585` | — | token\|agent |
| `DELETE /api/v1/route-collections/{slug}` | `operon/control_api.py:591` | — | token\|agent |
| `POST /api/v1/routes/import-archive` | `operon/control_api.py:602` | — | token\|agent |
| `POST /api/v1/workflows/import` | `operon/control_api.py:631` | — | token\|agent |
| `POST /api/v1/contracts` | `operon/control_api.py:646` | — | token\|agent |
| `POST /api/v1/graphs/export` | `operon/control_api.py:655` | — | token\|agent |
| `POST /api/v1/graphs/import` | `operon/control_api.py:673` | — | token\|agent |
| `POST /api/v1/plugins/refresh` | `operon/control_api.py:707` | — | token\|agent |
| `POST /api/v1/plugins/dependencies` | `operon/control_api.py:716` | — | token\|agent |
| `POST /api/v1/plugins/remove` | `operon/control_api.py:723` | — | token\|agent |
| `POST /api/v1/plugins/manage` | `operon/control_api.py:735` | — | token\|agent |
| `POST /api/v1/scripts/inspect` | `operon/control_api.py:747` | — | token\|agent |
| `POST /api/v1/scripts/extract` | `operon/control_api.py:769` | — | token\|agent |
| `GET /api/v1/operators/{identifier}/source` | `operon/control_api.py:781` | — | token\|agent |
| `POST /api/v1/scripts/publish` | `operon/control_api.py:787` | — | token\|agent |
| `GET /api/v1/jobs/{key}/exports/{index}` | `operon/control_api.py:818` | — | token\|agent |
| `POST /api/v1/execution/plan` | `operon/control_api.py:827` | — | token\|agent |
| `GET /api/v1/execution/resources` | `operon/control_api.py:833` | — | token\|agent |
| `POST /api/v1/remotes/{key}/refresh` | `operon/control_api.py:838` | — | token\|agent |
| `POST /api/v1/remotes/{key}/disconnect` | `operon/control_api.py:843` | — | token\|agent |
| `POST /api/v1/remotes/{key}/remove` | `operon/control_api.py:849` | — | token\|agent |
| `POST /api/v1/remotes/{key}/source` | `operon/control_api.py:855` | — | token\|agent |
| `POST /api/v1/remotes/{key}/library/check` | `operon/control_api.py:860` | — | token\|agent |
| `POST /api/v1/remotes/{key}/library/install` | `operon/control_api.py:865` | — | token\|agent |
| `GET /api/v1/service` | `operon/control_api.py:870` | — | token\|agent |
| `POST /api/v1/service/stop` | `operon/control_api.py:876` | — | token\|agent |

### `operon/bridge.py` (`/api/agent/*`)

| Method Path | Implementation | Callers | Auth |
| --- | --- | --- | --- |
| `GET /api/agent/identity` | `operon/bridge.py:70` | — | agent |
| `POST /api/agent/connect` | `operon/bridge.py:80` | — | agent |
| `GET /api/agent/connections` | `operon/bridge.py:92` | — | agent |
| `POST /api/agent/connections/disconnect` | `operon/bridge.py:97` | — | agent |
| `POST /api/agent/connections/revoke` | `operon/bridge.py:106` | — | agent |
| `POST /api/agent/connections/revoke-all` | `operon/bridge.py:115` | — | agent |
| `GET /api/agent/pool` | `operon/bridge.py:125` | — | agent |
| `POST /api/agent/pool/stop` | `operon/bridge.py:131` | — | agent |
| `GET /api/agent/remote` | `operon/bridge.py:140` | — | agent |
| `GET /api/agent/remote/summary` | `operon/bridge.py:145` | — | agent |
| `POST /api/agent/remote/{key}/ensure` | `operon/bridge.py:150` | — | agent |
| `POST /api/agent/remote/{key}/install` | `operon/bridge.py:155` | — | agent |
| `GET /api/agent/remote/{key}/setup` | `operon/bridge.py:174` | — | agent |
| `GET /api/agent/remote/{key}/library/plan` | `operon/bridge.py:179` | — | agent |
| `GET /api/agent/remote/{key}/library/status` | `operon/bridge.py:184` | — | agent |
| `POST /api/agent/remote/{key}/library/sync` | `operon/bridge.py:189` | — | agent |
| `GET /api/agent/remote/{key}/pool` | `operon/bridge.py:194` | — | agent |
| `POST /api/agent/remote/{key}/pool/stop` | `operon/bridge.py:199` | — | agent |
| `GET /api/agent/remote/{key}/environments` | `operon/bridge.py:204` | — | agent |
| `POST /api/agent/remote/{key}/environments/prepare` | `operon/bridge.py:209` | — | agent |
| `GET /api/agent/remote/{key}/environments/{name}/log` | `operon/bridge.py:216` | — | agent |
| `POST /api/agent/remote/{key}/environments/{name}/retry` | `operon/bridge.py:221` | — | agent |
| `POST /api/agent/remote/{key}/environments/{name}/cancel` | `operon/bridge.py:226` | — | agent |
| `POST /api/agent/remote/{key}/environments/{name}/dependencies/download` | `operon/bridge.py:231` | — | agent |
| `GET /api/agent/remote/{key}/resources` | `operon/bridge.py:237` | — | agent |
| `POST /api/agent/remote/{key}/resources/{name}/link` | `operon/bridge.py:242` | — | agent |
| `DELETE /api/agent/remote/{key}/resources/{name}/link` | `operon/bridge.py:251` | — | agent |
| `POST /api/agent/remote/{key}/resources/{name}/download` | `operon/bridge.py:256` | — | agent |
| `POST /api/agent/browse` | `operon/bridge.py:267` | — | agent |
| `POST /api/agent/remote/{key}/browse` | `operon/bridge.py:276` | — | agent |
| `GET /api/agent/sessions` | `operon/bridge.py:282` | — | agent |
| `POST /api/agent/sessions` | `operon/bridge.py:287` | — | agent |
| `GET /api/agent/sessions/{session}` | `operon/bridge.py:292` | — | agent |
| `POST /api/agent/sync` | `operon/bridge.py:297` | — | agent |
| `GET /api/agent/presence` | `operon/bridge.py:303` | — | agent |
| `GET /api/agent/context` | `operon/bridge.py:309` | — | agent |
| `POST /api/agent/apply` | `operon/bridge.py:313` | — | agent |
| `POST /api/agent/open` | `operon/bridge.py:322` | — | agent |
| `POST /api/agent/undo` | `operon/bridge.py:327` | — | agent |
| `GET /api/agent/events` | `operon/bridge.py:332` | — | agent |
| `GET /api/agent/transactions/{transaction_id}` | `operon/bridge.py:337` | — | agent |
| `GET /api/agent/stream` | `operon/bridge.py:342` | — | agent |
| `GET /api/agent/catalog` | `operon/bridge.py:362` | — | agent |
| `POST /api/agent/validate` | `operon/bridge.py:367` | — | agent |
| `POST /api/agent/sessions/{session}/run` | `operon/bridge.py:381` | — | agent |
| `GET /api/agent/jobs/{job}` | `operon/bridge.py:397` | — | agent |
| `POST /api/agent/jobs/{job}/cancel` | `operon/bridge.py:406` | — | agent |
| `GET /api/agent/plugins` | `operon/bridge.py:415` | — | agent |
| `POST /api/agent/plugins/install` | `operon/bridge.py:420` | — | agent |

## MCP and CLI parity

Columns: the control group from `Controls`, the MCP tool in `operon/mcp_server.py` that reaches the same capability, and the CLI verb in `operon/cli.py`. `—` means no equivalent exists, so that capability is only reachable through the HTTP surface the UI uses.

| Control group | MCP tool (`operon/mcp_server.py`) | CLI verb (`operon/cli.py`) |
| --- | --- | --- |
| 1-26 Environment list, prepare, repair/retry, cancel, log | `operon_environments` (:225), `operon_environments_prepare` (:237), `operon_environments_cancel` (:252), `operon_environment_retry` (:263), `operon_environment_log` (:271), `operon_environment_status` (:812) | `operon environment` (:224) |
| 19-20 Single-dependency install | `operon_environment_dependency_install` (:284) | `operon environment` (:224) |
| 22-24 Pool stop (local and remote) | `operon_pool_status` (:527), `operon_pool_stop` (:532), `operon_remote_pool_stop` (:537) | `operon pool` (:246) |
| 28-42 Large resources browse/download/link/unlink | `operon_resources` (:669), `operon_resource_download` (:684), `operon_resource_link` (:706), `operon_resource_unlink` (:726), `operon_resource_cancel` (:742), `operon_resource_log` (:747), `operon_resource_limits` (:817), `operon_browse` (:299) | `operon resources` (:234), `operon browse` (:367) |
| 43-73 Remote server connect/install/trust/refresh/disconnect/remove/source | `operon_remote_status` (:468), `operon_remote_save` (:897), `operon_remote_connect` (:902), `operon_remote_install` (:482), `operon_remote_install_status` (:498), `operon_remote_trust` (:910), `operon_remote_refresh` (:1096), `operon_remote_disconnect` (:1101), `operon_remote_remove` (:1106), `operon_remote_source` (:1111), `operon_remote_ensure` (:477) | `operon servers` (:316) |
| 68 Remote library check/plan/sync/status/install | `operon_remote_library_check` (:1121), `operon_remote_library_plan` (:503), `operon_remote_library_sync` (:513), `operon_remote_library_status` (:522), `operon_remote_library_install` (:1126) | `operon servers` (:316) |
| 74-83 Viewer defaults and paths | `operon_viewers` (:827), `operon_viewer_configure` (:832), `operon_viewer_default` (:838), `operon_viewer` (:430, opens a result in a viewer) | `operon viewers` (:310) |
| 85-109 Document/route save, export, import, library manage | `operon_workflows` (:108), `operon_workflow_save` (:114), `operon_workflow_import` (:1012), `operon_workflow_export` (:1018), `operon_routes` (:976), `operon_routes_register` (:981), `operon_routes_import_archive` (:1006), `operon_routes_import` (:781), `operon_library_state` (:986), `operon_library_manage` (:991), `operon_contracts` (:1024), `operon_graph_export` (:1029), `operon_graph_import` (:1034) | `operon workflow` (:212), `operon routes` (:362), `operon graph` (:266) |
| 112-113, 199-204 Plugin/operator-library management | `operon_plugins` (:892), `operon_plugins_refresh` (:1049), `operon_plugins_dependencies` (:1054), `operon_plugins_remove` (:1059), `operon_plugins_manage` (:1064), `operon_plugin_install` (:664), `operon_library_install` (:753), `operon_library_list` (:768), `operon_library_remove` (:773) | `operon plugin` (:352), `operon library` (:357) |
| 103 Canvas validation | `operon_validate` (:543), `operon_workflow_prepare` (:195) | `operon workflow` (:212) |
| 106-107, 146-152 Canvas prepare/run/export/history/outcome/cancel | `operon_canvas_prepare` (:916), `operon_canvas_status` (:922), `operon_canvas_cancel` (:927), `operon_canvas_execute` (:932), `operon_canvas_history` (:940), `operon_canvas_outcome` (:945) | `operon canvas` (:376) |
| 153-171 Plan panel compile/submit/status/artifacts/export | `operon_plan_compile` (:119), `operon_plan_submit` (:128), `operon_plan_status` (:137), `operon_plan_events` (:142), `operon_plan_attempts` (:148), `operon_plan_artifacts` (:154), `operon_plan_logs` (:160), `operon_plan_cancel` (:167), `operon_plan_export` (:172), `operon_plan_export_status` (:182), `operon_plan_export_cancel` (:190) | `operon plan` (:330) |
| 180-196 Job list, detail, cancel, logs, artifacts | `operon_jobs` (:333), `operon_job` (:634), `operon_cancel` (:659), `operon_logs` (:338), `operon_artifacts` (:343), `operon_artifact_table` (:351), `operon_result_files` (:357), `operon_job_parameters` (:822), `operon_job_export` (:1091), `operon_download_result` (:384), `operon_download_results` (:392), `operon_download_artifact` (:414), `operon_download_report` (:424) | `operon jobs` (:291), `operon artifacts` (:301), `operon run` (:280), `operon events` (:276) |
| 187-190 Step/report preview | `operon_artifacts` (:343), `operon_download_report` (:424), `operon_download_result` (:384) | `operon artifacts` (:301) |
| 205-216 Storage file picker | `operon_storage_status` (:887), `operon_browse` (:299) | `operon storage` (:321), `operon browse` (:367) |
| 177 Execution plan preview | `operon_execution_plan` (:1039), `operon_execution_resources` (:1044) | — |
| 102, 172-176 Execution target and settings | `operon_set_execution` (:575) | `operon graph` (:266) |
| 1, 88-100 Canvas sessions and undo/redo | `operon_sessions` (:76), `operon_context` (:81), `operon_graph` (:551), `operon_open` (:556), `operon_apply` (:563), `operon_undo` (:599), `operon_events` (:610), `operon_transaction_diff` (:619), `operon_run` (:628) | `operon sessions` (:197), `operon context` (:198) |
| 83/113 Catalog and operator lookup | `operon_catalog` (:86), `operon_operator_search` (:91), `operon_operator_describe` (:98), `operon_operator_source` (:1086) | `operon operators` (:201) |
| 197-198 Application preferences (appearance/language) | `operon_preferences` (:951), `operon_preferences_save` (:956) | — |
| 124 Runtime status panel aggregate | `operon_status` (:589), `operon_capabilities` (:786), `operon_engine_status` (:801), `operon_engine_events` (:806) | `operon engine` (:242), `operon capabilities` (:375) |
| — | `operon_guide` (:68), `operon_write_text` (:450), `operon_write_binary` (:458), `operon_task` (:442), `operon_service_status` (:791), `operon_service_stop` (:796) | `operon help` (:179), `operon serve` (:182), `operon service` (:184), `operon mcp` (:371), `operon schema` (:365), `operon registry` (:189), `operon script` (:257), `operon migrate` (:185) |

## Gaps

Each item states the control numbers, the evidence, and the impact. "Confirmed" means both sides were read; nothing here is inferred from naming alone.

1. **Remote environment log performs a retry (P0, `degraded`).** Controls 11 and 14. `src/web/remote_api.py:99` registers `@app.get('.../log')` and `:100` registers `@app.post('.../retry')` above the **same** function `def remote_environment_retry(key, name)` (`:101-102`). The intended `def remote_environment_log(key, name, limit=200)` at `:104-105` has no decorator. Impact: opening the remote log drawer (or pressing `刷新` inside it) re-triggers a retry on the remote host and returns a retry payload instead of a log; users see an empty log and a silently restarted install. `manager.environment_log` exists (`src/web/remote_service.py:542`), so only the wiring is wrong.
2. **`POST /api/jobs` is dead code from the UI's point of view (P1).** `api.run` (`frontend/src/api.ts:396`) has zero call sites (`grep -rho 'api\.[a-zA-Z]*' frontend/src | sort | uniq -c` shows no `api.run`); the `运行` button (`frontend/src/App.tsx:1392`) only opens `CanvasPlanDialog`, and the real run is `POST /api/v1/canvas-plans/prepare` + `/execute` (`operon/canvas_api.py:25`, `:42`). Impact: the studio job API and the canvas plan path can drift apart with no test noticing, and `/api/jobs` history for canvas runs depends on the canvas path writing the same records.
3. **`operon_remote_source` accepts only `profile_id` (P1, MCP parity).** Control 68 passes `(path, reader)` to `POST /api/remote/{key}/source` (`frontend/src/RemotePanel.tsx:177` → `src/web/remote_api.py:159`), but the MCP tool is `operon_remote_source(profile_id: str)` (`operon/mcp_server.py:1111`). The repository already pins this with `tests/test_mcp_source_passthrough.py:84` (`xfail(reason="known gap: operon_remote_source accepts only profile_id")`). Impact: an agent cannot resolve a remote path to a source descriptor the way the UI can, so remote inputs reachable from the browser are unreachable from MCP.
4. **Remote job detail depends on a local cache (`degraded` risk).** `GET /api/jobs/{key}` routes remote ids through `service.details` → `self.remotes.job(key)` (`src/web/service.py:1685-1686`); `RemoteManager.reference` raises `KeyError('找不到远程运行记录，请连接服务器刷新。')` when the persisted summary is missing (`src/web/remote_service.py:625`). Impact: controls 180-183 and 194-195 show an empty pane with a refresh hint after the cache is cleared, even though the job still exists on the remote host. There is no `GET /api/remote/{key}/jobs/{id}` route to fall back to (`grep -rn 'jobs/' src/web/remote_api.py` returns only `/api/remote/{key}/environments/...`).
5. **Dependency rows are counted from the manifest, not from the installer plan (P1 correctness).** `dependencies()` flattens six manifest keys with **no dedup** (`src/web/environment_api.py:202-212`), and `augment()` sets `dependency_total = len(rows)` / `dependency_installed = sum(installed)` (`:317-318`). The installer records its own totals separately (`operon/environment_install.py:240-241`, `:286-287`). Impact: a package listed under both `requirements` and `pip_wheels` counts twice, so the readiness card can show e.g. `18/20` while the installer reports `19/19`; the UI's progress bar and the log disagree.
6. **Environment readiness is downgraded by resource completeness, silently.** `snapshot()` rewrites `status='ready'` to `'incomplete'` and sets `item['error']='资源未齐备（x/y）：…'` whenever `resources_ready < resources_total` (`src/web/environment_api.py:457-466`), while `resource_counts()` only counts resources declared in the environment manifest (`:367-415`). Impact: "install finished but the environment says incomplete" is expected behaviour, but the two counters (`dependency_*` vs `resources_*`) are presented side by side with no explanation, and `availableActions('incomplete')` (`frontend/src/RuntimeStatusPanel.tsx:144-151`) offers repair rather than resource download.
7. **Resource "no download source" is decided client-side from one boolean.** `unit['download_supported']` is computed server-side as `bool(covered) or bool(rsync) or any(download.unit == unit.name)` (`src/web/resource_api.py:360`), and the button both disables and relabels to `无下载源` when `download_supported === false && !rsync` (`frontend/src/LargeResourceSection.tsx:115-130`). Impact: when the fallback match at `:320-361` fails to associate a declared download with its unit, the UI offers no action at all and gives no reason; there is no route that reports *why* a unit has no source.
8. **`重试` on a result does not retry.** Control 190 (`frontend/src/Results.tsx:525`) re-fetches the job/step; no POST is issued, and no `/api/jobs/{key}/retry` route exists. Impact: a user pressing it after a failure sees the same failure again.
9. **No frontend caller for several destructive or diagnostic routes.** `POST /api/resources/{name}/cancel` (`src/web/resource_api.py:936`), `GET /api/resources/operations/{job_id}` (`:943`), `GET /api/resources/{name}/log` (`:950`), `POST /api/plugins/install` (`src/web/plugin_api.py:133`), `POST /api/plugins/remove` (`:167`), `POST /api/plugins/manage` (`:177`), `POST /api/environments/{name}/repair` (`src/web/environment_api.py:736`). Impact: an in-flight resource download cannot be cancelled from the UI, and a failed download has no log viewer, even though both endpoints exist.
10. **`unclear` rows. None remain: the three earlier unknowns are traced in place - `归档` writes through `planApi.saveState` to `POST /api/v1/plan-ui-state` (`operon/plan_ui_state.py:102-104`); both import controls (`frontend/src/PlanPanel.tsx:57-66`, `:166`) are renderer-only state changes with no HTTP call.

### Route-missing check

No control row carries the `route missing` status. Every `HTTP` cell in `Controls` points at a registering decorator that is listed in `Backend endpoints`, so no frontend path in this audit failed to resolve on the backend. The three `unclear` rows are not missing routes: their request body could not be traced (gap 10). Any future frontend call that adds a path must be checked against the decorator inventory before this statement is trusted again.

## Verification recipes

All recipes assume `BASE=http://127.0.0.1:<port>` from the running Studio instance and, for mutating studio routes, `STUDIO_TOKEN` copied from the bootstrap call. `GET` recipes need no token; `/api/v1/*` recipes accept either the studio token or an agent bearer token. Replace `{key}` with the profile id returned by `GET /api/remote`.

**Environment list and readiness (controls 1-3, 124).**
```bash
curl -s "$BASE/api/environments" | jq '.environments[] | {name, status, dependency_installed, dependency_total, resources_ready, resources_total, error}'
```
Expect one object per environment; `status` transitions `queued → installing → ready`, or `incomplete` with an `error` starting `资源未齐备`. If `dependency_total` disagrees with the count printed by the install log, gap 5 is present.

**Prepare (controls 3, 5, 18, 26).**
```bash
curl -s -X POST "$BASE/api/environments/prepare" -H "x-studio-token: $STUDIO_TOKEN" -H 'content-type: application/json' -d '{"names":["<env>"]}' | jq '{prepared, status}'
```
Expect `prepared[0] = {name, job, status}` and a `job` id. A typo in the body field name returns `422` with `不认识的字段…`.

**Cancel (controls 8, 12, 13).**
```bash
curl -s -X POST "$BASE/api/environments/<env>/cancel" -H "x-studio-token: $STUDIO_TOKEN" | jq '{cancelled, job, completed, reason, status}'
```
Expect `cancelled:true` while installing; after completion expect `cancelled:false` with `reason` `该环境已完成安装，取消无效。`. Remote variant: `POST /api/remote/{key}/environments/<env>/cancel`.

**Retry / repair (controls 6, 10).**
```bash
curl -s -X POST "$BASE/api/environments/<env>/retry" -H "x-studio-token: $STUDIO_TOKEN" | jq '{job, status}'
curl -s -X POST "$BASE/api/remote/{key}/environments/<env>/retry" -H "x-studio-token: $STUDIO_TOKEN" | jq .
```
The remote call must return a retry payload; if the *log* endpoint returns the same shape, the decorator collision in gap 1 is still present.

**Dependency install (controls 19, 20).**
```bash
curl -s -X POST "$BASE/api/environments/<env>/dependencies/download" -H "x-studio-token: $STUDIO_TOKEN" -H 'content-type: application/json' -d '{"kind":"pypi","requirement":"numpy==1.26.4"}' | jq '{status, job, name}'
```

**Log (controls 7, 11, 14).**
```bash
curl -s "$BASE/api/environments/<env>/log?limit=200" | jq 'type, (if type=="object" then keys else length end)'
curl -s "$BASE/api/remote/{key}/environments/<env>/log?limit=200" | jq .
```
The local call returns the progress log (JSON or text). The remote call is expected to return a log; if it returns a retry/status payload instead, gap 1 is reproduced.

**Resources catalogue and "no download source" (controls 28, 31).**
```bash
curl -s "$BASE/api/resources" | jq '.resources[] | .units[]? | {name, state, download_supported, rsync, files_present, files_missing}'
```
Every unit the UI renders as `无下载源` must have `download_supported:false` and `rsync:false`; anything else means the client and server disagree.

**Resource download / link / unlink / browse (controls 29-31, 34-40).**
```bash
curl -s -X POST "$BASE/api/resources/<name>/download" -H "x-studio-token: $STUDIO_TOKEN" -H 'content-type: application/json' -d '{"unit":"<unit>"}' | jq .
curl -s -X POST "$BASE/api/resources/<name>/link" -H "x-studio-token: $STUDIO_TOKEN" -H 'content-type: application/json' -d '{"source":"/data/ref","replace":true,"unit":"<unit>"}' | jq .
curl -s -X DELETE "$BASE/api/resources/<name>/link?unit=<unit>" -H "x-studio-token: $STUDIO_TOKEN" | jq .
curl -s -X POST "$BASE/api/browse" -H "x-studio-token: $STUDIO_TOKEN" -H 'content-type: application/json' -d '{"path":"/data"}' | jq '{path, parent, roots, entries: (.entries|length)}'
```
`link` on a filesystem without link support returns `501` (`LinkUnsupported`); `browse` truncates `entries` at 500.

**Remote connect and execution-position switch (controls 1, 56-62).**
```bash
curl -s -X POST "$BASE/api/remote/profiles" -H "x-studio-token: $STUDIO_TOKEN" -H 'content-type: application/json' -d '{"name":"gpu","host":"10.0.0.5","username":"ops","port":22,"auth":"key"}' | jq '.id'
curl -s -X POST "$BASE/api/remote/{key}/connect" -H "x-studio-token: $STUDIO_TOKEN" -H 'content-type: application/json' -d '{}' | jq .
curl -s "$BASE/api/remote/{key}/environments" | jq '.environments[]? | {name, status}'
```
A first connect against an unknown host returns `409` with `{"code":"host_key_required","fingerprint":"…"}`; repeat after `POST /api/remote/{key}/trust` with that fingerprint. Switching the panel's `执行位置` (control 1) issues the same `GET /api/remote/{key}/environments` as the last command.

**Run a canvas (controls 107, 148, 149).**
```bash
curl -s -X POST "$BASE/api/v1/canvas-plans/prepare" -H "x-studio-token: $STUDIO_TOKEN" -H 'content-type: application/json' -d '{"graph":<graph>,"request_id":"<uuid>"}' | jq '{status, phase, digest}'
curl -s "$BASE/api/v1/canvas-plans/status?request_id=<uuid>" | jq '{status, phase}'
curl -s -X POST "$BASE/api/v1/canvas-plans/execute" -H "x-studio-token: $STUDIO_TOKEN" -H 'content-type: application/json' -d '{"preparation_id":"<id>","request_id":"<uuid>","action":"run"}' | jq .
```
Expect `status` `preparing → ready`; executing before `ready` is refused inside `canvas_plans.execute` (`operon/canvas_plans.py:281`). A graph that needs a portable tool returns `422` with `code: "portable_tool_required"` and `next_actions` (`operon/environment_store/closures.py:38`).

**Cancel a canvas preparation (control 148).**
```bash
curl -s -X POST "$BASE/api/v1/canvas-plans/cancel" -H "x-studio-token: $STUDIO_TOKEN" -H 'content-type: application/json' -d '{"request_id":"<uuid>"}' | jq .
```
Only effective while `status === 'preparing'` (`operon/canvas_plans.py:92`).

**Task list and job detail (controls 180-196).**
```bash
curl -s "$BASE/api/jobs" | jq '.[0:5] | .[] | {id, status, created_at}'
curl -s "$BASE/api/jobs/<id>" | jq 'keys'
curl -s -X POST "$BASE/api/jobs/<id>/cancel" -H "x-studio-token: $STUDIO_TOKEN" | jq .
```
`GET /api/jobs` truncates to 60 records (`src/web/api.py:407`). For an `ssh-`-prefixed id, a `404` with `unknown job or resource operation` while the job still exists on the remote host is gap 4.

**Cancel a running job from the task list (control 196).**
```bash
curl -s -X POST "$BASE/api/jobs/<id>/cancel" -H "x-studio-token: $STUDIO_TOKEN" -H 'content-type: application/json' | jq .
curl -s "$BASE/api/jobs/<id>" | jq '.status'
```
Expect `status` to move to `cancelled`; a remote job that is missing from the local cache returns `404` (gap 4).

**Remote log regression check (gap 1).**
```bash
curl -s "$BASE/api/remote/{key}/environments/<env>/log" | jq 'keys'
```
A retry payload (no log text, but a job/status field) means the collision at `src/web/remote_api.py:99-105` is still present.
