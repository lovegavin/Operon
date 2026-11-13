# 应用侧变更总览：Operon Studio 3.1.6 → 5.1.5

- 基线：`v3.1.6` = `0f2c87cd`
- 终点：`v5.1.5` = `5073a9a9`（`main` 与 `origin/main` 一致，tag 已推送）
- 区间提交：476 个（不含 merge 455 个），其中非 `library/` 改动 452 个
- 应用发版：4.0.0–4.0.10、4.1.0–4.1.9、4.2.0–4.2.4、5.0.0–5.0.1、5.1.0–5.1.5
- 算子库关系：3.1.6 时代仍与 `library-v7.0.1` 同仓；5.x 起库独立版本（0.0.0 / 0.1.0）
- 协议：`protocol_version=3`、`protocol_revision=3.7` 全程未变

> 这份文档只讲**应用侧**变化。算子库一侧的改动见
> `02-library-changes-7.0.1-to-0.1.0.md`；当前架构见
> `03-current-state-and-decoupling.md`。

## 1. 4.0.x：从 BioPipe 迁移到原生 Operon

4.0.0 是分水岭：应用不再保留 `biopipe` 兼容别名、旧模块、旧 bundle 路径或旧文件格式。

| 版本 | 主题 | 关键变化 |
|---|---|---|
| 4.0.0 | 原生品牌 + 8.0.1 库 | `operon.*` 取代 `biopipe.*`；`.operon-library.zip` 是唯一接受的库包；路线集合按一个 `.zip` 导入并自动注册 |
| 4.0.1 | 服务端安装/更新 | 桌面端可安装/升级远端 server；UI 与安装流程打通 |
| 4.0.2 | 工作区 | workspace 语义与安装目录分离 |
| 4.0.3 | 强制升级/卸载 | 旧 server 空闲则退役；有任务时正常升级停止；强制升级取消任务并清池；卸载先断开 MCP |
| 4.0.4–4.0.6 | 稳定性 | 安装器、路线导入提示、启动与卸载细节修复 |
| 4.0.7 | 准入/就绪/内存 | admission 失败回写 failed；readiness 绑定 graph digest；关闭内存管理不再占满整池；remote prepare 离线可用；`/api/remote` 状态瘦身 |
| 4.0.8 | 安装器根目录 + 远端输入 | `--install-dir` 精确作为根目录；本地输入文件可为远端运行暂存 |
| 4.0.9 | 共享池升级 | 服务端共享池切换与远端运行状态 |
| 4.0.10 | 安装位置与 pin | 安装器根目录规则、远程旧 pin 刷新、池升级、远端状态 |

这一阶段的中心是“应用可用性”：安装、卸载、升级、共享池、准入与 readiness 从 3.x 的实验状态变成可交付行为。

## 2. 4.1.x：环境模型与远程可控性

4.1.0 引入“库声明环境，应用负责创建”的模型，之后围绕它修了多轮。

- **4.1.0 环境清单随库分发**：`.operon-library.zip` 带 `sources/operon/environments.json`；声明 `resources.environment` 的算子通过 `EnvironmentStep` 进入独立解释器；导入后后台准备缺失/过期环境；环境使用 per-env 锁、staging 目录、原子 rename、receipt。
- **4.1.1**：修旧 source tree 缺 `environments.json` 导致导入崩溃；环境改为**显式安装**（导入时不再自动装）；最小化保留任务栏。
- **4.1.2**：跨平台 wheel 校验修复（按条目比较，忽略 zip 中央目录平台字段与 RECORD 行序）。
- **4.1.3**：安装/卸载提示与“根目录除 workspace 全删”一致；删除独立“隔离环境”面板，环境安装并入“修复依赖”；本地远端都确认可检查/补齐；修远端图执行时本地重复装环境。
- **4.1.4**：安装包 runtime 里的 `operon` 版本错配修复，MCP 入口不再解析到 3.1.8；打包时校验 runtime 版本。
- **4.1.5**：环境准备改为后台任务、无超时、写进度文件；运行时基础依赖随包安装；新增“运行状态”面板（本地池、任务、环境进度、服务器状态）。
- **4.1.6**：远程共享池可见（版本、PID、closing、会话数、活动任务）。
- **4.1.7**：服务端增加 `environments` / `environments_prepare` / `environments_log` RPC；MCP 增加 `profile_id` 直连指定服务器；显式 bootstrap `setuptools`；失败保留 `.failed-*` 现场；文档补 OpenMM。
- **4.1.8**：更新即全量替换（先断连、清池、删旧版本）；隔离环境迁到安装根 `environments/` 并在升级后保留；隔离执行链修 provider 路径、probe cwd、`code_root` 指向 site-packages 导致的 NumPy ABI 冲突；内置 8.0.7。
- **4.1.9**：CSV/文件产物分页读取、复合图 `offset/limit` 透传、`operon_job` 等待上限调整、旧画布 pin 自愈、`setuptools` 引导。

这一阶段的教训：**环境是库的声明，不是应用的猜测**；任何“共享解释器回退”都会在 OpenMM/NumPy 这类强 ABI 依赖上炸掉。

## 3. 4.2.x：任务目录、工作区写入与 pin 语义

- **4.2.0**：结果从 `.studio` 移到任务目录：
  ```text
  <workspace>/<task>/input/
  <workspace>/<task>/results/<job-id>/
  ```
  `.studio/jobs/<id>/` 只留启动器状态。旧文档的 `base_dir` 不迁移，旧任务继续可跑。
- **4.2.1**：文件产物 `/file` 默认返回真实文件（此前返回 `files.json`）；`operon_job` 等待上限提高；远端环境不可用提示。
- **4.2.2**：新增 `operon_task`（建 `input/results/reports/figures`）与 `operon_write_text`（后端代写，绕开宿主 shell 的低完整性限制）；文件产物下载修复；`operon_job` 等待上限 120s；库升到 8.0.9。
- **4.2.3**：路线导入 pin 改为“可证明才迁移，否则 422 拒绝”，不再调用宽松的 `refresh_missing`。
- **4.2.4**：新增 `operon_write_binary`（base64、50 MiB、路径校验）；远端诊断文案；库升到 8.0.10。

这一阶段确立了三条边界：
1. 结果属于任务目录，不属于应用内部状态；
2. 写文件可以由后端代理，但路径必须在 workspace 内；
3. pin 迁移只能基于可证明对应关系，不能用来给错误发布兜底。

## 4. 5.0.x：库/应用解耦

5.0.0 是第二次分水岭：库从应用仓库的“内置 seed”变成独立发布物。

- **两个 ZIP 的导入契约**：
  - 算子库：`operon-library-v0.0.0.operon-library.zip`
  - 路线库：`operon-routes-v0.0.0.zip`
- 应用 payload **不再包含 `library/seed`**；首次使用必须导入库（5.1.4 起改为自带一个 base 库）。
- 应用只做四件事：校验、安装 wheel、注册描述符、执行；**不再计算或改写 `code_sha` / entry point**。
- 8.x 旧库被明确拒绝：
  `This library bundle uses the legacy 8.x format.`
  不做静默 pin 修复，也没有旧读取路径。
- 远程 provisioning 随之上线：源码包携带库 bundle，服务端用 `install_library` 安装，不再要求 Python 侧 seed。

5.0.1 修了三件事：库放到 `<install>/versions/<ver>/library`（workspace 只放数据）、扩展名统一为 `.operon-library.zip`、画布去掉 pin（运行时按 id 在当前库中解析）。

## 5. 5.1.x：多库、可复现与交付闭环

| 版本 | 主题 | 关键变化 |
|---|---|---|
| 5.1.0 | 多算子库 + provenance | 等地位分支（`main-v0.1.0`、`fork1-v0.0.0`）；每个任务记录实际用到的算子/Reader 版本与哈希；`<task>/runs/<job-id>/` 可复现骨架 |
| 5.1.1 | UI 文案 | 去掉 `0.0.x` 版本化文件名与路线搜索框，只显示支持的扩展名 |
| 5.1.2 | 库身份来自库包 | `library.json` 增加 `library_name`；标签由 `<name>-v<version>` 生成；删除导入时的名称/版本输入；主名称重复即拒绝 |
| 5.1.3 | 远端安装修复 | `build_identity` 改读 `library/registry.json`；源码包携带各分支 archive；服务端安装全部库并把 `library_root` 传入 `Settings` |
| 5.1.4 | base 库 + 路线直导 + 身份缓存 | 安装包内置 `library/base` 并在首次启动自动装成 `main-v0.1.0`；导入路线集合后直接可用（去掉勾选/“添加到算子库”）；库变更后刷新远端 build 缓存 |
| 5.1.5 | 路线集合命名 | 路由集合改为 `operon-routes-<name>-v<version>.zip`；修前端只认旧文件名导致的误报；修路线列表乱码 |

5.1.x 的三个用户可见结果：
1. 新安装即有 `main-v0.1.0`，不需要先导入库；
2. 多个库可以共存，但 id/包/模块/主名称不得重叠；
3. 每次运行都能在任务目录里找到“用了哪些算子、哪个库、什么哈希”。

## 6. 发版与资产（应用侧）

| 版本 | GitHub release id | 备注 |
|---|---:|---|
| 5.0.0 | 444076071 | 首次两 ZIP 契约 |
| 5.1.0 | 444291945 | 多库 + provenance |
| 5.1.1 | 444313412 | UI 文案 |
| 5.1.2 | 444344861 | 库名来自库包 |
| 5.1.3 | 444389057 | 远端安装修复 |
| 5.1.4 | 444410008 | base 库 |
| 5.1.5 | 444430872 | 当前 latest |

5.1.5 资产：
- `Operon_Setup-5.1.5.exe`：396,123,856 B，`d7ab0167a6a7076c22162b91ddc7036cd1bbd0473d4d6aa7bd9325d4e00bbca5`
- `Operon-5.1.5-Server.zip`：9,125,292 B，`adbb8281c7d5b69eaf866ec42111fc1dbb4b015165b8628193d220af8e980ed3`
- `operon_studio-5.1.5-py3-none-any.whl`：669,548 B，`af1d73a80a74076b135e463983591ca7825090a2e971ad29ff20f03c69a18cae`
- `SHA256SUMS.txt`：282 B

## 7. 兼容与升级

- 应用与库的协议契约：`protocol_version=3`；库必须声明 `bundle_format=1` 且 `minimum_application` 满足。
- 8.x 库：拒绝，给出迁移提示。
- 5.0 之前的工作区：`_legacy_library_state()` 会清掉旧 registry 状态，避免 UI 显示一个已经不存在的 8.0.10。
- 单库时代的安装：迁移为 `v<version>` 分支（或 `main` 名称），不复制、不重装。
- 路线集合：新命名与旧命名都能导入；但路线里的 pin 必须与当前库的 `code_sha` 精确一致，否则拒绝。
- 旧画布：没有 pin；运行时按 id 解析。旧任务的结果与 runs 不受影响。

## 8. 已知边界

- Windows 打包依赖 .NET 8、Python 3.12、Node 22；`package_release.py` 必须传 `--desktop <目录>`，`--base-library` 才会带上 base 库。
- GitHub 发布走 `scripts/release_proxy`（本机 18080），git push 走同一代理；直连在部分网络下不可用。
- 远端共享池的库状态依赖 `library_root` 持久化；5.1.3 之前的服务端在升级后可能仍读到旧 receipt。
- 5.1.5 之后没有跑完整 Windows 全量套件；发布验收以定向测试与安装/运行验证为主。
