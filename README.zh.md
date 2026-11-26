# Operon

**契约优先的生物信息学工作流 —— 可视化、可脚本化、可被 Agent 操作。**

**一句话，一个平台，少量 token。** 用一句话说清要做的分析，由 Agent 从经过校验的算子中组出流程，Operon 在真正运行之前完成校验，同一个引擎记录下每份结果由什么产生。上下文只花在用到的那几步上，而不是整个算子库上。

Operon Studio 5.11.2 · Operator Library 2.1.3 · Apache-2.0

[English](README.md) · [10 分钟上手](QUICKSTART.zh.md) · [Quick start (EN)](QUICKSTART.en.md) · [文档](docs/README.md) · [发布记录](https://github.com/lovegavin/Operon/releases) · [许可证](LICENSE)

---

## 为什么要有 Operon

大多数生物信息学分析是由 shell 脚本、notebook 和一次性 Python 拼起来的。这样能用，直到一年后有人要重跑这条流程、交给合作者，或者要向审稿人解释某张图到底是哪个工具版本产出的。

Operon 把**分析当作数据，而不是代码**。一个工作流是一张由带类型的步骤组成的图，每个步骤的输入、输出、参数和运行时需求都是显式的；每个步骤都来自一个经过校验的算子，它的契约只声明一次，并在算子库构建时接受检查。

这带来四个脚本拼不出来的性质：

- **没有需要信任的生成代码。** 你组合的是已声明的算子，不必在数据被触碰之前审查模型写出的代码。
- **可复现是构造出来的。** 每次运行都随附参数快照、算子库代次、环境收据和产物哈希。
- **一个引擎，多个入口。** 桌面画布、CLI、HTTP API 和 MCP 服务驱动同一套工作流存储、调度器、内存准入和执行环境，而不是四个各自实现。
- **Agent 只加载用到的部分。** 发现只有三层——一个指南主题、算子摘要、再到真正用到的那几个算子的 schema——token 成本随工作流规模增长，而不是随算子库规模增长。

**算子库才是产品本身**，界面只是抵达它的方式。

## 你能得到什么

| 方面 | 能力 |
| --- | --- |
| **可视化画布** | 通过连接算子卡来组合工作流；编辑参数、查看 schema、保存版本，整张画布的修改作为一次可撤销的事务提交。 |
| **算子库** | 1,000+ 个经过校验的算子和 100+ 个 Reader，覆盖统计、机器学习、序列与组学、结构与基因组、表观组、质量控制、系统发生、蛋白质组、代谢组、单细胞、Hi-C、微生物组、分子对接、因果推断和可视化。 |
| **工作流路由** | 79 条现成的 route 模板（比对 QC、ATAC/ChIP 流程、组装 QC、密码子设计与偏好、注释、ML 基线等），可以打开、改造并另存。 |
| **执行** | 本地环境、显式的依赖准备、内存准入、磁盘/流式资源协议、可续传的传输、SSH 服务器，以及带容量感知选点的 Slurm 集群。 |
| **结果** | 运行历史、保留的输出表、内置结果查看器、发表级图表与静态绘图。 |
| **可移植导出** | 把一个运行计划冻结成独立包，在没有安装 Operon 的机器上也能跑。 |
| **自动化** | 带版本的 HTTP API、可脚本化的 CLI，以及带渐进式文档、工作区文件与作业回报的 MCP 工具。 |

## 四个入口，一个服务

| 入口 | 怎么用 | 适合什么 |
| --- | --- | --- |
| 桌面 Studio | Windows 安装包，或在浏览器里 `operon serve` | 搭建、检查和调试分析 |
| CLI | `python -m operon …` | 批处理、服务器、可复现命令 |
| HTTP API | `operon serve`、`/api/v1/openapi.json` | 前端页面、LIMS 与流程集成 |
| MCP | `operon mcp` | 组合并运行工作流的 Agent |

MCP 是协议桥，不是 AI 供应商：Operon 从不调用任何模型。你可以连接任意支持 MCP 的客户端，只在确实要执行时给 `--allow-run`，只做查看时用 `--read-only`。

发现路径是特意按机器最省的方式设计的：`operon_guide` 一次只返回一个主题并按 sha256 缓存，`operon_operator_search` 只返回摘要而不是实现，`operon_operator_describe` 只给当前用到的那几个算子的 schema。

## 安装

| 目标 | 做法 |
| --- | --- |
| Windows 桌面 | 运行 `Operon_Setup.exe`。它自带可重定位的 CPython 运行时、隔离的应用配置，并使用经过签名校验的 WebView2 bootstrapper。 |
| Linux / 无头服务器 | 解压 `Operon-<version>-Server.zip` 后执行 `install.sh --prefix <dir>`（见 [command_line_installation.md](docs/command_line_installation.md#linux-server)），或者 `pip install . ./library`。 |
| 源码检出 | `python -m pip install '.[agent]'`（Python 3.11+），需要 MCP 时加上 `agent` extra。 |
| Agent 客户端 | 在你的 MCP 客户端配置里启动 `operon mcp`，见 [agent_operations.md](docs/agent_operations.md)，以及可直接粘贴的 [roles/agent.md](docs/roles/agent.md)。 |

无论哪种安装，都可以这样自检：

```text
operon --version        # Operon 5.11.2
operon capabilities     # API 版本、协议版本与能力清单
operon registry check   # 当前算子库的算子、Reader、包与路由数量
```

Windows 安装会把工作区放在安装目录下，共享配置放在 `%USERPROFILE%\.operon`；Linux 和 macOS 使用 `~/.operon`。大型模型权重、数据库、外部工具和专用环境都按需准备，安装包从不隐含它们。

## 第一次运行：桌面版（5 分钟）

1. 启动 Operon，打开画布。
2. 拖入一个 Reader，指向一张表 —— 例如 `CsvReader` 读取 `matrix.csv`，维度 `sample,feature`，样本标签用 `auto`，列标签取表头。
3. 加入一个算子，比如 `PCA`，把 Reader 的输出接到它上面，维度设为 `feature`，主成分数量设为 `2`。
4. 打开执行设置，检查环境并按需准备缺失的依赖。
5. 运行。在任务管理器里跟踪任务；环境准备始终是一个显式步骤，不会被悄悄执行。
6. 打开结果查看器，然后到运行历史里查看参数、日志和保留的输出。

结果查看器在 **设置 → 输出与查看器** 里配置。子图可以折叠、单个算子可以旁路，整张画布的编辑作为一次可撤销事务提交；而“开始运行”永远是一个独立动作。

## 第一次运行：无头模式

```text
python -m pip install . ./library
operon --version
operon serve --port 8765     # 然后打开 http://127.0.0.1:8765
```

也可以不启浏览器，直接用 CLI 驱动同一个服务：

```text
operon operators search "differential expression"
operon operators describe pca --view schema
operon workflow lint examples/workflows/script_pipeline/workflow.yaml
operon environment check examples/workflows/script_pipeline/workflow.yaml --require-files
operon run examples/workflows/script_pipeline/workflow.yaml --progress --request-id demo-001
operon jobs list
```

`environment check` 只校验声明与输入文件；`environment prepare` 才是明确授权安装的动作。校验与准备永远不会自动安装。

## 一次运行是如何组成的

1. **图** —— 步骤、端口和标签定义计算内容；已保存的工作流携带自己冻结的参数值。
2. **就绪检查** —— 提交前校验契约、参数与输入文件；缺少内核或文件会在这一步带着诊断信息提前失败。
3. **环境** —— 声明的环境先检查、再显式准备，并以收据的形式与本次运行一起记录。
4. **执行** —— 调度器在本地、SSH 远端或 Slurm 节点上运行步骤，执行内存准入、资源模式和溢出限制。
5. **产物** —— 输出按表示形式、大小和 SHA-256 建立索引，再通过结果查看器展示或导出。
6. **导出** —— 冻结的计划可以连同已验证的环境一起打包，在目标机器上脱离 Operon 运行。

## 算子库

捆绑的算子库与应用独立版本化。本源码树声明应用 **5.11.2**、算子库 **2.1.3**（最低应用版本 5.11.2）。

算子和 Reader 使用 **SDK 协议 v3**：字面类声明、独立的参数 schema、相邻的 Markdown 文档、声明的端口，以及内容哈希的实现。注册表会拒绝无法编译的声明、读取了未声明参数的声明，以及引用了不存在算子的 route。

与其相信 README 里的一个数字，不如直接查你自己的库：

```text
operon registry check
operon operators list --kind reader
operon operators describe <id> --view docs
```

第三方算子以包的形式存在。用 `operon plugin init/check/test/build` 构建，在 **算子库管理 → 刷新算子库** 里热加载单个模块，或用 `operon library install` 安装签名过的库。应用与算子库的分界见 [library_extensions.md](docs/library_extensions.md) 和 [application_library_boundary.md](docs/application_library_boundary.md)。

## 仓库布局

| 路径 | 内容 |
| --- | --- |
| `operon/` | 应用：服务、CLI、HTTP API、MCP 服务、执行引擎、环境、远端协调、存储与共享池。 |
| `operon_sdk/` | 面向协议 v3 Step 与 Reader 的公共 SDK。 |
| `src/` | 捆绑算子库导入的实现包：`src/task/step/steps/`、`src/reader/readers/`、`src/core/` 里的共享契约、`src/web/` 里的服务端辅助。 |
| `library/seed/` | 生成的算子库：注册表索引、文档、route 模板与包清单。 |
| `frontend/` | React 19 + Vite 画布界面。 |
| `desktop/`、`installer/` | Windows 桌面宿主与安装器。 |
| `docs/` | 文档；从 [docs/README.md](docs/README.md) 开始。 |
| `examples/` | 协议 v3 示例与一个示例工作流。 |
| `tests/`、`scripts/`、`verification/` | 测试套件、构建与发布工具、验收证据。 |

## 文档导引

| 我想…… | 读这里 |
| --- | --- |
| 先跑起来 | [quickstart.md](docs/quickstart.md)、[installation.md](docs/installation.md)、[windows_setup.md](docs/windows_setup.md)、[desktop.md](docs/desktop.md)、[command_line_installation.md](docs/command_line_installation.md) |
| 编写工作流 | [workflow_yaml_v3.md](docs/workflow_yaml_v3.md)、[workflow_parameters.md](docs/workflow_parameters.md)、[data_formats.md](docs/data_formats.md)、[readiness.md](docs/readiness.md) |
| 控制执行 | [EXECUTION_ENVIRONMENTS.md](docs/EXECUTION_ENVIRONMENTS.md)、[resource_runtime.md](docs/resource_runtime.md)、[server_cli.md](docs/server_cli.md) |
| 在远端运行 | [REMOTE_EXECUTION.md](docs/REMOTE_EXECUTION.md)、[SERVER_HANDSHAKE.md](docs/SERVER_HANDSHAKE.md)、[SERVER_INSTALL_REPAIR.md](docs/SERVER_INSTALL_REPAIR.md) |
| 交付结果 | [result_viewers.md](docs/result_viewers.md)、[PUBLICATION_FIGURES.md](docs/PUBLICATION_FIGURES.md)、[automatic_portable_export.md](docs/automatic_portable_export.md)、[portable_packages_v3.md](docs/portable_packages_v3.md) |
| 集成或自动化 | [headless_api.md](docs/headless_api.md)、[api_quickstart.md](docs/api_quickstart.md)、[agent_operations.md](docs/agent_operations.md)、[roles/agent.md](docs/roles/agent.md)、[canvas_collaboration.md](docs/canvas_collaboration.md) |
| 扩展算子库 | [operator_protocol.md](docs/operator_protocol.md)、[sdk_quickstart.md](docs/sdk_quickstart.md)、[sdk_reference.md](docs/sdk_reference.md)、[plugins.md](docs/plugins.md)、[library_release_standard.md](docs/library_release_standard.md) |
| 跟进变更 | [docs/releases/](docs/releases/) |
| 理解设计 | [docs/design/](docs/design/)、[five-layer-test-standard.md](docs/verification/five-layer-test-standard.md) |

完整索引：[docs/README.md](docs/README.md)。

## 开发

```text
python -m pip install -e '.[dev]'
python -m pytest -q                          # 全量测试
python -m pytest tests/test_contracts.py -q  # 指定测试
cd frontend && npm ci && npm run build       # 构建画布前端
python -m operon registry check              # 算子库一致性检查
```

只要改动了算子元数据，就要重建静态注册表与算子文档（见 [registry_maintenance.md](docs/registry_maintenance.md)）：

```text
python -m operon registry build
python scripts/build_operator_docs.py
```

纯文档改动不得改变执行身份，也不应迫使用户重新固定工作流版本。产品内的路径要保持可移植，技术文档使用英文。

## 发布模型

`main` 集成应用与捆绑算子库，两者按各自的语义版本与标签发布：

- 应用发布使用 `v<major>.<minor>.<patch>`；
- 算子库发布使用 `library-v<major>.<minor>.<patch>`。

每个应用版本记录它构建时使用的确切算子库源码，每个库声明能加载它的最低应用版本。已发布的标签与安装包不可变。重算算子库是一次有意的、版本化的操作 —— 应用侧的文档或打包修复不会悄悄改写 seed。

## 状态

Operon 以验收证据发布，而不是在本文件里做承诺。证据标准在 [five-layer-test-standard.md](docs/verification/five-layer-test-standard.md)，各版本的审计报告在 [docs/verification/](docs/verification/)。算子数量、平台支持与覆盖率会随版本和已安装的算子库而变化；`operon registry check` 与 `operon capabilities` 才会给出你这棵源码树的真实情况。

## 开源许可

Operon 以 [Apache License 2.0](LICENSE) 发布，Copyright 2026 Haojian Li。分发时请保留 `LICENSE` 与 `NOTICE`，并查看 [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES) 中的捆绑组件。欢迎贡献，见 [CONTRIBUTING.md](CONTRIBUTING.md)。
