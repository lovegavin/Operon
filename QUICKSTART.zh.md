# 10 分钟跑通 Operon

这是一份“照着点就行”的说明。只做一件事：用一张很小的表格跑一次 PCA，确认软件能用。

你不需要会 Python，不需要装 Conda，也不需要 AI 账号。示例数据是编造的，只用于检查流程，不代表任何生物学结论。

## 你需要准备

- Windows 10 或 11，最好有 8 GB 内存。
- 能上网。第一次检查运行环境时，可能需要下载几个科学计算包。
- 一个可写的安装位置，例如 `D:\Operon Studio`。不要选 `C:\Program Files`，也不要选需要管理员权限的目录。

## 第 1 步：安装

1. 打开 [Releases](https://github.com/lovegavin/Operon/releases/latest)。
2. 下载 **Operon_Setup.exe**。不要下载名字里带 `Server` 或 `Library` 的文件。
3. 双击安装包。如果 Windows 弹出蓝色提示，点“更多信息” → “仍要运行”。
4. 安装目录填 `D:\Operon Studio`，点“安装”。
5. 安装完成后，勾选“打开 Operon”，点完成。

第一次启动会慢一点，等窗口完全出来再操作。后端和前端都准备好后，窗口底部会显示已连接。

## 第 2 步：准备一张小表

在桌面新建一个文本文件，名字改成 `matrix.csv`，内容完全照抄下面七行：

```csv
gene_a,gene_b,gene_c
1,2,3
2,3,4
4,1,2
3,4,1
5,2,6
6,5,3
```

注意：第一行是列名，后面六行是数字；逗号是英文逗号。

## 第 3 步：把表读进来

1. 在 Operon Studio 左侧点 **添加输入数据**。
2. 选择刚才的 `matrix.csv`。
3. Reader 选 **CsvReader**。
4. 维度填 `sample, feature`（英文逗号，前后不要加空格）。
5. 标签用默认的“自动”即可；勾选“首行是列名”。
6. 点确认。画布上会出现一个输入节点。

## 第 4 步：加 PCA

1. 在左侧算子库搜索框输入 **PCA**。
2. 把 **PCA** 拖到画布上，放在输入节点右边。
3. 用鼠标从输入节点右侧的小圆点拖一条线到 PCA 左侧的小圆点。
4. 双击 PCA：
   - 维度选 `feature`；
   - 主成分数量填 `2`；
   - 其他参数保持默认。
5. 点确认。

## 第 5 步：检查环境并运行

1. 点右上角 **运行设置**。
2. 执行位置选 **本地**。
3. 点 **检查运行环境**。
4. 如果提示缺少依赖，点 **准备环境/安装依赖**，等它完成，再检查一次。
5. 回到画布，点 **运行**。
6. 等任务变成“已完成”。打开 **运行历史** → **查看结果**。

你应该能看到一个完成了的任务，里面有 PCA 结果和两个主成分。这个例子不会自动画散点图；需要图的话，再拖一个绘图算子接在 PCA 后面。

## 第 6 步（可选）：在 Linux 服务器上跑

只有当你确实有一台 Linux 服务器时才做这一步。Windows 本机用户可以直接跳过。

1. 在 Releases 下载 **Operon-4.0.5-Server.zip**，上传到服务器。
2. 在服务器上执行：

```sh
unzip Operon-4.0.5-Server.zip
cd Operon-4.0.5-Server
bash install.sh --prefix "$HOME/operon" --result "$PWD/server-install.json"
```

3. 安装结果会给出 `install_dir`、`workspace` 和 `command`。用这些真实路径替换下面的示例：

```sh
"$HOME/operon/bin/operon" --version
"$HOME/operon/bin/operon" workflow lint "$HOME/operon/workspace/quickstart/workflow.yaml"
"$HOME/operon/bin/operon" run "$HOME/operon/workspace/quickstart/workflow.yaml" --progress --brief
```

更完整的服务器说明见 [命令行安装](docs/command_line_installation.md#linux-server)。

## 遇到问题先看这里

- **窗口一直白屏**：等 1–2 分钟；仍然不行就完全退出再开。不要同时开很多个 Operon。
- **检查环境失败**：先确认能上网，再点“准备环境”。公司网络需要代理时，先在系统代理里配好。
- **安装时提示目录不可写**：换到 `D:\Operon Studio` 这类普通目录，不要用 `C:\Program Files`。
- **想卸载**：在 Windows“应用”里卸载，或运行安装目录里的 `Operon_Uninstall.exe`。4.0.5 会保留 `<安装目录>\workspace` 里的工作区和分析结果，确认不需要后再手动删除。
- **日志在哪**：`%USERPROFILE%\.operon\profiles\<profile-id>\logs\desktop-YYYYMMDD.log`。

## 接下来

- [完整文档](docs/README.md)
- [Windows 安装与隔离目录](docs/windows_setup.md)
- [命令行与 Linux 服务器](docs/command_line_installation.md)
- [工作流 YAML](docs/workflow_yaml_v3.md)
- [English quick start](QUICKSTART.en.md)

Operon 使用 Apache-2.0 许可证，可自由使用、修改和再分发；见 [LICENSE](LICENSE) 与 [NOTICE](NOTICE)。
