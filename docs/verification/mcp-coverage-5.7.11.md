# MCP 前端操作对等覆盖审计（5.7.11）

基线：`release/5.4.0` / `9d332d86f`；审计日期 2026-11-20。

## 结论

- `frontend/src/api.ts` 的 106 个方法全部有结论：65 个由既有 MCP 工具覆盖，33 个本轮新增，2 个等价映射到 `operon_write_binary`，6 个明确不适用（原因见文末）。
- MCP 工具总数：107 → **141**（+34）；`@server.tool()` 名称无重复。
- 新增 33 条 `/api/v1` 控制面路由，全部经 `authorize(request, scope)` 鉴权，与桌面 HTTP 使用同一 bridge 能力模型。
- 修复 `operon_environment_retry` 的运行期缺陷：原实现调用不存在的 `client.post()` 且路径重复带 `/api`，任何重试都会抛 `AttributeError`。
- 测试：`tests/test_parity_control_plane.py` + `tests/test_mcp_server.py` 共 **96 passed**（58 + 38）。

## 覆盖表

| 前端方法 | MCP 工具 | 状态 |
| --- | --- | --- |
| `catalogIfChanged` | `operon_catalog` | OK（全量返回；无 generation 304 优化） |
| `inspectScript` | `operon_script_inspect` | 新增 |
| `extractScript` | `operon_script_extract` | 新增 |
| `publishScript` | `operon_script_publish` | 新增 |
| `operatorSource` | `operon_operator_source` | 新增 |
| `prepareEnvironment` | `operon_workflow_prepare_environment` | OK |
| `checkEnvironment` | `operon_workflow_check_environment` | OK |
| `environments` | `operon_environments` | OK |
| `prepareEnvironments` | `operon_environments_prepare` | OK |
| `remoteEnvironmentRetry` | `operon_environment_retry` | OK（本轮修复运行期缺陷） |
| `retryEnvironment` | `operon_environment_retry` | OK（同上） |
| `environmentLog` | `operon_environment_log` | OK |
| `cancelEnvironment` | `operon_environments_cancel` | OK |
| `version` | `operon_version` | 新增 |
| `pool` | `operon_pool_status` | OK |
| `stopPool` | `operon_pool_stop` | OK |
| `remotePoolStop` | `operon_remote_pool_stop` | OK |
| `remoteEnvironments` | `operon_environments` | OK |
| `remotePrepareEnvironments` | `operon_environments_prepare` | OK |
| `remoteEnvironmentDependencyDownload` | `operon_environment_dependency_install` | OK |
| `remoteCancelEnvironment` | `operon_environments_cancel` | OK |
| `remoteEnvironmentLog` | `operon_environment_log` | OK |
| `remoteResources` | `operon_resources` | OK |
| `remoteLinkResource` | `operon_resource_link` | OK |
| `remoteUnlinkResource` | `operon_resource_unlink` | OK |
| `savePreferences` | `operon_preferences_save` | 新增 |
| `viewers` | `operon_viewers` | OK |
| `configureViewer` | `operon_viewer_configure` | OK |
| `defaultViewer` | `operon_viewer_default` | OK |
| `artifactViewers` | `operon_viewer` | OK（viewer 省略时列出候选） |
| `openViewer` | `operon_viewer` | OK（传 viewer 时打开） |
| `prepareViewer` | `operon_viewer_prepare` | OK |
| `executionPlan` | `operon_execution_plan` | 新增 |
| `executionResources` | `operon_execution_resources` | 新增 |
| `remoteStatus` | `operon_remote_status` | OK |
| `saveRemote` | `operon_remote_save` | OK |
| `connectRemote` | `operon_remote_connect` | OK |
| `installRemote` | `operon_remote_install` | OK |
| `refreshRemote` | `operon_remote_refresh` | 新增 |
| `checkRemoteLibrary` | `operon_remote_library_check` | 新增 |
| `installRemoteLibrary` | `operon_remote_library_install` | 新增 |
| `remoteLibraryStatus` | `operon_remote_library_status` | OK |
| `remoteLibraryPlan` | `operon_remote_library_plan` | OK |
| `syncRemoteLibrary` | `operon_remote_library_sync` | OK |
| `remoteSetup` | `operon_remote_install_status` | OK |
| `trustRemote` | `operon_remote_trust` | OK |
| `disconnectRemote` | `operon_remote_disconnect` | 新增 |
| `removeRemote` | `operon_remote_remove` | 新增 |
| `browsePath` | `operon_browse` | OK |
| `browseRemote` | `operon_browse` | OK |
| `largeResources` | `operon_resources` | OK |
| `largeResourceLink` | `operon_resource_link` | OK |
| `largeResourceUnlink` | `operon_resource_unlink` | OK |
| `largeResourceDownload` | `operon_resource_download` | OK |
| `remoteResourceDownload` | `operon_resource_download` | OK |
| `environmentDependencyDownload` | `operon_environment_dependency_install` | OK |
| `storageRoots` | `operon_storage_roots` | OK |
| `browseStorage` | `operon_storage_browse` | OK |
| `statStorage` | `operon_storage_stat` | OK |
| `previewStorage` | `operon_storage_preview` | OK |
| `closeStorageBrowse` | `operon_storage_close` | OK |
| `sourceRemote` | `operon_remote_source` | 新增 |
| `plugins` | `operon_plugins` | OK |
| `refreshPlugins` | `operon_plugins_refresh` | 新增 |
| `repairDependencies` | `operon_plugins_dependencies` | 新增 |
| `openPluginFolder` | `—` | 不适用：在桌面宿主调用 os.startfile/xdg-open 打开文件管理器，MCP 无 GUI 语义 |
| `pluginOperation` | `—` | 不适用：旧异步 operation 轮询；MCP 变更工具同步返回最终状态 |
| `removePlugin` | `operon_plugins_remove` | 新增 |
| `managePlugin` | `operon_plugins_manage` | 新增 |
| `installPlugin` | `operon_plugin_install` | OK |
| `libraries` | `operon_library_list` | OK |
| `installLibrary` | `operon_library_install` | OK |
| `deleteLibrary` | `operon_library_remove` | OK |
| `routeCollections` | `operon_route_collections` | 新增 |
| `deleteRouteCollection` | `operon_route_collection_remove` | 新增 |
| `agent` | `—` | 不适用：原始 fetch 逃生舱，不是用户操作；等价于 client.request |
| `catalog` | `operon_catalog` | OK |
| `workspace` | `operon_workspace` | 新增 |
| `saveWorkspace` | `operon_workspace_save` | 新增 |
| `workflows` | `operon_workflows` | OK |
| `workflow` | `operon_workflows` | OK（workflow_id 参数） |
| `prepareWorkflow` | `operon_workflow_prepare` | OK |
| `exportWorkflow` | `operon_workflow_export` | 新增 |
| `importWorkflow` | `operon_workflow_import` | 新增 |
| `saveWorkflow` | `operon_workflow_save` | OK |
| `importRouteArchive` | `operon_routes_import_archive` | 新增 |
| `importRouteCollection` | `operon_routes_import` | OK |
| `routes` | `operon_routes` | 新增 |
| `libraryState` | `operon_library_state` | 新增 |
| `manageLibrary` | `operon_library_manage` | 新增 |
| `registerRoutes` | `operon_routes_register` | 新增 |
| `bootstrap` | `—` | 不适用：桌面启动换取 x-studio-token 的会话握手；MCP 在 connect 阶段用 bridge secret 换 Bearer token |
| `validate` | `operon_validate` | OK |
| `contracts` | `operon_contracts` | 新增 |
| `export` | `operon_graph_export` | 新增 |
| `import` | `operon_graph_import` | 新增 |
| `run` | `operon_submit` | OK |
| `history` | `operon_jobs` | OK |
| `job` | `operon_job` | OK |
| `cancel` | `operon_cancel` | OK |
| `preview` | `operon_artifacts` | OK（preview=true） |
| `step` | `operon_job_export` | 新增 |
| `url` | `—` | 不适用：客户端 URL 拼接，无服务端操作 |
| `uploadFiles` | `—` | 不适用：浏览器 File 批处理协议；MCP 用 operon_write_binary 逐文件写入 |
| `uploadReference` | `operon_write_binary` | OK（等价：base64 写入工作区） |
| `upload` | `operon_write_binary` | OK（等价：base64 写入工作区） |

## 授权对等

- **本地链路**：MCP 进程由 `operon mcp` 启动，`Client.connect()` 用实例密钥 `X-Operon-Bridge` 调 `POST /api/agent/connect` 换取 Bearer token；token 的作用域由启动参数决定（`context`，可加 `edit` / `run` / `plugins`）。`bridge.actor()` 对每个路由校验所需 capability，缺失时返回 403 与 `Agent connection requires the '<cap>' capability.`。
- **新增路由**：全部在 `operon/control_api.py` 内调用 `authorize(request, scope)`；读操作 `context`，写操作 `edit`，插件/环境/库安装 `plugins`，作业提交/取消与远程连接 `run`。没有一条新增路由绕过鉴权。
- **远程链路**：所有远程 MCP 工具都要求 `profile_id`，并只调用 `/remote/{id}/...` 或 `/v1/remotes/{id}/...`，由 `RemoteService` 走已授权的 SSH 通道；没有工具直接拼 SSH 命令。`profile_id` 为空的工具（`operon_resources` 等）与前端一致，默认本地。
- **为什么新增 v1 而不是复用 `/api`**：`src/web/api.py:90-99` 的中间件要求非 GET 的 `/api/*` 请求必须带 `x-studio-token`；MCP 只有 Bearer agent token。新增 v1 路由既保持桌面 token 边界，又让 MCP 复用同一 `JobService`，不引入旁路。
- **错误语义**：`authorize` 的 403 与 HTTP 相同；远程 `RemoteError` 中仅 `host_key_required` 映射 409，其余 422，与 `src/web/remote_api.py` 一致。作业/流程写操作的 409 revision conflict 由既有 v1 处理器保持。

## 新增工具与授权范围

| MCP 工具 | 路由 | 作用域 |
| --- | --- | --- |
| `operon_preferences` | `GET /api/v1/preferences` | `context` |
| `operon_preferences_save` | `POST /api/v1/preferences` | `edit` |
| `operon_workspace` | `GET /api/v1/workspace` | `context` |
| `operon_workspace_save` | `POST /api/v1/workspace` | `edit` |
| `operon_version` | `GET /api/v1/version` | `context` |
| `operon_routes` | `GET /api/v1/routes` | `context` |
| `operon_routes_register` | `POST /api/v1/routes/register` | `edit` |
| `operon_library_state` | `GET /api/v1/library/state` | `context` |
| `operon_library_manage` | `POST /api/v1/library/manage` | `edit` |
| `operon_route_collections` | `GET /api/v1/route-collections` | `context` |
| `operon_route_collection_remove` | `DELETE /api/v1/route-collections/{slug}` | `edit` |
| `operon_routes_import_archive` | `POST /api/v1/routes/import-archive` | `edit` |
| `operon_workflow_import` | `POST /api/v1/workflows/import` | `edit` |
| `operon_workflow_export` | `POST /api/v1/workflows/export` | `context` |
| `operon_contracts` | `POST /api/v1/contracts` | `context` |
| `operon_graph_export` | `POST /api/v1/graphs/export` | `context` |
| `operon_graph_import` | `POST /api/v1/graphs/import` | `edit` |
| `operon_execution_plan` | `POST /api/v1/execution/plan` | `context` |
| `operon_execution_resources` | `GET /api/v1/execution/resources` | `context` |
| `operon_plugins_refresh` | `POST /api/v1/plugins/refresh` | `plugins` |
| `operon_plugins_dependencies` | `POST /api/v1/plugins/dependencies` | `plugins` |
| `operon_plugins_remove` | `POST /api/v1/plugins/remove` | `plugins` |
| `operon_plugins_manage` | `POST /api/v1/plugins/manage` | `plugins` |
| `operon_script_inspect` | `POST /api/v1/scripts/inspect` | `edit` |
| `operon_script_extract` | `POST /api/v1/scripts/extract` | `edit` |
| `operon_script_publish` | `POST /api/v1/scripts/publish` | `plugins` |
| `operon_operator_source` | `GET /api/v1/operators/{identifier}/source` | `context` |
| `operon_job_export` | `GET /api/v1/jobs/{key}/exports/{index}` | `context` |
| `operon_remote_refresh` | `POST /api/v1/remotes/{key}/refresh` | `edit` |
| `operon_remote_disconnect` | `POST /api/v1/remotes/{key}/disconnect` | `edit` |
| `operon_remote_remove` | `POST /api/v1/remotes/{key}/remove` | `edit` |
| `operon_remote_source` | `POST /api/v1/remotes/{key}/source` | `context` |
| `operon_remote_library_check` | `POST /api/v1/remotes/{key}/library/check` | `context` |
| `operon_remote_library_install` | `POST /api/v1/remotes/{key}/library/install` | `plugins` |

## 不适用项

- `openPluginFolder`：在桌面宿主直接调用 `os.startfile` / `xdg-open` 打开文件管理器，没有可返回的 JSON 资源；MCP 客户端并非桌面宿主。
- `pluginOperation`：旧接口的异步 operation 轮询。MCP 的 `plugins_refresh` / `plugins_remove` / `plugins_manage` 同步完成并返回最终状态，不需要 operation id。
- `uploadFiles`：浏览器 `File` 批处理协议（先建 batch、逐文件 octet-stream、再 complete）。MCP 用 `operon_write_binary` 逐文件写入工作区，语义等价且不依赖浏览器。
- `url`：纯客户端 URL 拼接，无服务端操作。
- `bootstrap`：桌面启动时用 `/api/bootstrap` 换 `x-studio-token` 的会话握手；MCP 的对等鉴权发生在 `connect`（bridge secret → Bearer token），不是用户操作。
- `agent`：原始 fetch 逃生舱，不是用户操作；MCP 侧对应 `client.request()`，不暴露为工具。

## 测试

```
cd /home/gavin/Operon-540
/home/gavin/miniconda3/envs/operon/bin/python -m pytest \
  tests/test_parity_control_plane.py tests/test_mcp_server.py -q
```

结果：`96 passed, 2 warnings in 11.50s`。

`tests/test_mcp_server.py` 覆盖：34 个新工具的路由/载荷转发（`NEW_FORWARDS` 32 条 + 下载与 DELETE 两条单独用例）、工具总数 141、`environment_retry` 回归、以及 33 条新 v1 路由的 `authorize` 作用域静态断言。另有 1 条端到端用例在临时 headless app 上验证 `context`/`edit`/`plugins` 三种 agent scope 的 200/403 语义。
