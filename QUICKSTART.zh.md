# Operon 快速开始

从一台干净机器到跑完一个分析：安装 Operon Studio 5.11.2 与自带的算子库 2.1.3，
先跑通一个真实分析，再把同一份工作流搬到命令行。

安装包自带算子库，没有单独的导入步骤。

## 1. 安装

| 目标 | 做什么 |
| --- | --- |
| Windows 10/11 x64 | 运行 `Operon_Setup.exe`。它自带 Python 运行时，不需要系统 Python。 |
| Linux 服务器 | 解压 `Operon-<version>-Server.zip`，执行 `./install.sh --prefix "$HOME/operon" --result` |
| 源码仓库 | `python -m pip install . ./library`，然后 `operon serve --port 8765` |

确认你手上到底是哪个构建：

```bash
operon --version
operon capabilities
```

`operon --version` 会打印 `Operon 5.11.2`。`operon capabilities` 列出这个构建真正
能做的事；仓库里的页面如果和它不一致，以构建为准。

## 2. 在画布上跑第一个分析

准备一个 CSV：行是样本，列是特征。

```text
sample,A,B,C
s1,1.0,2.5,3.1
s2,1.4,2.1,2.8
s3,9.2,8.7,9.9
```

1. 在 Studio 里选一个工作区目录，把 CSV 放进去。
2. 把 **CsvReader** 拖到画布上并指向该文件。它把表头读成特征名，把第一列读成样本标签。
3. 把 **PCA** 拖到画布上，连接 CsvReader 的输出，把 `dimension` 设为 `feature`，
   `components` 设为 `2`。
4. 点 **运行**。Operon 会校验图、解析算子环境、执行，并把参数、环境与日志和结果一起留下。
5. 用查看器打开结果。查看器在 **设置 → 输出与查看器** 里配置。

编辑和运行是两件事：画布可以随便改，没有点运行就不会执行。

## 3. 用命令行做同一件事

CLI 和桌面、HTTP API 用的是同一个服务：

```bash
operon operators search pca
operon operators describe pca --view schema
operon workflow lint examples/workflows/script_pipeline/workflow.yaml
operon environment check examples/workflows/script_pipeline/workflow.yaml --require-files
operon run examples/workflows/script_pipeline/workflow.yaml --progress --request-id quickstart-001
operon jobs list
```

`environment check` 不会安装任何东西。准备环境是另一个显式步骤
（`operon environment prepare`），因为它会改动这台机器。

## 4. 接下来看什么

| 想做的事 | 读什么 |
| --- | --- |
| 整体理解产品 | [README.zh.md](README.zh.md) |
| 命令参考与日常使用 | [docs/roles/user.md](docs/roles/user.md) |
| 让 Agent 驱动 Operon | [docs/roles/agent.md](docs/roles/agent.md) |
| 用 YAML 写工作流 | [docs/workflow_yaml_v3.md](docs/workflow_yaml_v3.md) |
| 在 Linux 服务器上运行 | [docs/REMOTE_EXECUTION.md](docs/REMOTE_EXECUTION.md) |
| 把结果交付给没有 Operon 的人 | [docs/automatic_portable_export.md](docs/automatic_portable_export.md) |
| 完整文档索引 | [docs/README.md](docs/README.md) |

English quick start: [QUICKSTART.md](QUICKSTART.md)
