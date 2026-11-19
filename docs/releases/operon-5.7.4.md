# Operon Studio 5.7.4

Released 2026-11-19.

This release is a control audit release: every interactive control that
changes state was traced from the React handler to the HTTP route to the
Python implementation, for both the local installation and a remote server.

## Fixed

- F-59: cancelling a remote environment did nothing. The panel returned early
  for remote targets and the server agent had no `environments_cancel`
  method. The agent now stops the installer process, records the
  cancellation and answers with a fresh environment snapshot.
- F-60: the environment log button always read the local log, even when a
  server was selected. Remote targets now fetch the server log.
- F-61: dependency installation inside an environment had no remote path, so
  clicking install with a server selected installed into the local machine.
  The agent now exposes `environments_dependency` and the panel routes the
  action to the selected execution location.
- F-62: with no GPU the installer fetched CUDA torch wheels. CUDA pins are
  now dropped and `https://download.pytorch.org/whl/cpu` is used.
- F-63: the environment card kept a fixed percentage while pip installed
  dependencies, because only the environment creation step reported bytes.
  Installer output is streamed and pip download sizes are parsed, so the
  progress bar and the elapsed label move through dependency installation.

## Control audit

The audit covered the runtime status panel, the large resource section, the
remote library panel, the server panel, the results panel and the task list.
For each control the table below lists the handler, the endpoint and the two
execution locations.

| Control | Frontend handler | Endpoint | Local | Remote |
| --- | --- | --- | --- | --- |
| 刷新 | `onRefresh` | `GET /api/environments` | yes | `GET /api/remote/{key}/environments` |
| 全部安装 | `onPrepareAll` | `POST /api/environments/prepare` | yes | `/api/remote/{key}/environments/prepare` |
| 准备 | `act('prepare')` | same as above, `names:[name]` | yes | yes |
| 取消 | `act('cancel')` | `POST /api/environments/{name}/cancel` | yes | `/api/remote/{key}/environments/{name}/cancel` |
| 查看日志 | `loadLog` | `GET /api/environments/{name}/log` | yes | `/api/remote/{key}/environments/{name}/log` |
| 依赖安装 | `runDependency` | `POST /api/environments/{name}/dependencies/download` | yes | `/api/remote/{key}/environments/{name}/dependencies/download` |
| 停止共享池 | `stopPool` | `POST /api/pool/stop` | yes | `/api/remote/{key}/pool/stop` |
| 资源下载 | `onDownload` | `POST /api/resources/{name}/download` | yes | `/api/remote/{key}/resources/{name}/download` |
| 资源链接 | `onLink` | `POST /api/resources/{name}/link` | yes | `/api/remote/{key}/resources/{name}/link` |
| 解除链接 | `onUnlink` | `DELETE /api/resources/{name}/link` | yes | `DELETE /api/remote/{key}/resources/{name}/link` |
| 浏览目录 | `loadPicker` | `POST /api/browse` | yes | `POST /api/remote/{key}/browse` |
| 检查算子库 | `check` | `GET /api/remote/{key}/library/check` | n/a | yes |
| 强制同步算子库 | `sync` | `POST /api/remote/{key}/library/sync` | n/a | yes |
| 安装服务端 | `onInstall` | `POST /api/remote/{key}/install` | n/a | yes |
| 连接 / 断开 | `connect` / `disconnect` | `POST /api/remote/{key}/connect` / `disconnect` | n/a | yes |
| 浏览服务器文件 | `browse` | `POST /api/remote/{key}/browse` | n/a | yes |
| 取消任务 | `onCancel` | `POST /api/jobs/{id}/cancel` | yes | local job list only |
| 预览结果 | `preview` | `GET /api/jobs/{id}/artifacts/{a}/preview` | yes | local job list only |

Remaining known gaps, documented rather than silently ignored:

- The task list and the results panel address local jobs only; jobs executed on
  a server are inspected through the plan results panel of that server.
- Resource downloads on a server cannot be cancelled from the desktop yet; the
  agent has no `resources_cancel` method.
- `operon environment status <name>` still resolves against the working
  directory, so the CLI form differs from `operon environment list`.

## Notes

- CPU fallback keeps the pins for packages that are unrelated to torch; only
  `torch`, `torchvision`, `torchaudio` and similar pins are rewritten.
- A dependency installed on a server stays on that server; the local
  environment is untouched.
