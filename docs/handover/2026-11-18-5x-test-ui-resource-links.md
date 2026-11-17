# 交接文档：5.x 全量测试、运行状态 UI 重做、资源外链（2026-11-18）

这份文档给“在同一个工作区新开的对话”用。目标是把 5.4.8 这条 Python 线做扎实：全量
测试、把发现的 bug 修掉、重做“运行状态”界面、加上“外部资源/权重链接”能力，然后按
既有发布流程出 5.4.9（或 5.5.0）。中途不要等我确认，自己迭代、自己验证、自己记录。

---

## 1. 任务边界（用户原话要点）

1. **只做 5.x（Python 版本）**，不做 Rust/Tauri 迁移（`experimental/tauri-shell` 的评估
   已结束，交接在 `docs/handover/2026-11-17-tauri-6.0.0-migration.md`，不要继续动它）。
2. **做一次全量测试**：干净安装、用 MCP 装环境、跑通路线（本地 + 远程 + GPU）、
   资源下载/链接、UI 交互。遇到 bug 自行修复并做（实机）测试。
3. **重做“运行状态”界面**，现在太丑；要好用、好看，仍然在 5.x 分支上改。
4. **新增资源/权重外链**：把别处（例如 srv 上的 AF2 数据库与权重）的目录或文件
   **链接**进 Operon 的资源目录，不拷贝，使环境依赖等价于“已经下载/拷贝”。
5. 装机终验由用户本人执行；我只负责修、测、打包、发行、给 `D:\download` 路径与哈希。
6. 用户明确“我不会喊停”：不要每步问，按本文第 5 节的顺序推进，直到 bug 清单清零。

---

## 2. 当前坐标（先核对再动手）

| 项 | 值 |
|---|---|
| 5.x 工作树 | `/home/gavin/Operon-540`，分支 `release/5.4.0` |
| 5.x HEAD | `837996c2d`（5.4.8 代码是 `24778beff`，其后两个是交接文档提交） |
| 已发行版本 | **5.4.8**，release `448812716`，`latest = v5.4.8` |
| 库/路线 | `main-v0.1.28`（1177 descriptors / 1069 operators / 108 readers）、`operon-routes-main-v0.1.28.zip`（79 条） |
| 主仓库 | `/home/gavin/Operon`（库分支 `library/resource-download-interface`，不要在此改应用侧） |
| 构建树 | `D:\OperonBuild547`（5.4.8 全链产物）；`D:\OperonBuild540\dotnet`（.NET 8.0.428）、`D:\OperonBuild540\builder`（打包 venv） |
| 便携解释器 | `D:\OperonBuild547\portable\python`（3.11.18） |
| 下载交付目录 | `D:\download` |
| 用户自用安装 | `D:\Operon Studio` —— **绝对不要动**（进程、目录、profile 都不碰） |
| 测试安装 | `D:\OperonTest5xx`（必须放 D 盘；C 盘只剩约 28 GB） |
| MCP 配置 | `C:\Users\梦天曦\.dsh\profiles\desktop\cordis.patch.yml`（改到当前测试安装的 `runtime\python\python.exe`） |
| 远端 | `lihj@172.22.148.93`，managed root `/public/home/lihj/Operon`，workspace `/public/home/lihj/Operon/workspace`，profile id `df1ff559c6fd474ca2d11a88f12a9bc7` |
| 远端资源 | `/public/home/lihj/operon-resources/{alphafold2,colabfold,boltz,esmfold,openfold,rfdiffusion,...}`，`~/.local/share/operon/resources/*` 已是指向它们的软链 |
| GPU | 本机 RTX 3090 24 GB；srv 也是 3090 24 GB |

先跑这三条确认没有漂移：

```bash
cd /home/gavin/Operon-540 && git log --oneline -3 && git status --short
ls "D:/OperonBuild547/portable/python/python.exe" "D:/OperonBuild547/runtime548/python/python.exe"
curl -s http://127.0.0.1:<port>/api/version
```

---

## 3. 5.4.8 已经做了什么（避免重复劳动）

- 画布/路线**不与 pin 绑定**：`operon/pins.py::strip_pins()` 在导入时摘掉
  `plugin_lock`，原 pin 只写进 `collections/<slug>.json` 的 `pins` 字段作溯源；
  两个导入入口（`/api/routes/import-collection`、`/api/v1/routes/import-archive`）
  行为一致；运行只按算子 id 在当前库里解析。
- 算子库调色板**只渲染单一来源**（本机或某台已连接服务器），面板头部有“算子库来源”
  下拉；圆圈按钮 = “重新读取算子库”（不再跳服务器设置）。
- 桌面宿主首启等待从 **90 s 提到 300 s**（`desktop/Program.cs:207`），避免首启安装
  基础库时超时。
- `_bootstrap_base_library` 不再用 marker 短路（库被清空但 marker 还在时会重装）。
- 路线库支持**按包卸载**：`GET/DELETE /api/route-collections`，manifest 在
  `<workspace>\.studio\workflows\collections\<slug>.json`。

对应文档：`docs/releases/operon-5.4.8.md`、`docs/design/route-collections.md`。

---

## 4. 全量测试计划（按顺序做，每阶段留证据）

证据统一放 `docs/releases/operon-5.4.9-test-report.md`（新建），每条含：阶段、命令/请求、
job id、耗时、结果、失败时的错误原文。**没有证据的项一律记为未测。**

### 阶段 0：基座（干净安装）

1. `Start-Process Operon_Setup-5.4.8.exe --quiet --install-dir D:\OperonTest5xx --no-register`
   （用 `-Wait -PassThru` 读退出码；PowerShell 会把安装器 stderr 当 `NativeCommandError`，
   不要据此判失败）。
2. 校验：版本目录、`installation.json`、`package-manifest.json`、`operon --version`。
3. 启动桌面版，确认 300 s 内进入；再确认 `/api/version`、`/api/bootstrap`、
   `/api/libraries` 都有数据（基础库 `main-v0.1.28` 1177 descriptors）。
4. **无图形验证通道**（本项目最有用的一套）：
   - `D:\OperonTest5xx\run_srv.py`：`subprocess.Popen([...desktop_server.py...],
     stdin=subprocess.PIPE)` 并 `proc.wait()` —— `desktop_server.py` 见到 stdin EOF 会
     立刻关停，直接 `Start-Process` 一定“startup complete → Shutting down”。
   - 取 token：`GET /api/bootstrap` 里的 `token`（43 字符），写文件后用 `curl.exe`
     带 `X-Studio-Token`（PowerShell 5.1 的 `Invoke-WebRequest` 非交互不可用，
     `Invoke-RestMethod` 会因 JSON 重复键报 `DuplicateKeysInJsonString`）。
   - 页面验证用无头 Edge + CDP：`--headless=new --remote-debugging-port=96xx
     --user-data-dir=D:\OperonTest5xx\edge`，配一个最小 WebSocket 客户端
     （参考 `D:\OperonBuild547\cdp_lib.py`，只用标准库）。

### 阶段 1：本地 MCP 工具面

对 `operon_status / operon_guide / operon_operator_search / operon_operator_describe /
operon_workflows / operon_validate / operon_submit / operon_job / operon_jobs /
operon_logs / operon_artifacts / operon_artifact_table / operon_result_files /
operon_download_result(s) / operon_resources / operon_environment(s) / operon_remote_*`
逐个真实调用一次，记录返回形状与错误处理。重点检查：

- `operon_submit` 之后立刻返回 job id，`operon_job` 能查到 running/complete；
- 作业产物落在 `job.json` 的 `output_dir` 下（`.../results/<req>/runs/<run>/steps/`），
  不在 `.studio/jobs/<id>`；
- `operon_download_result` 落盘到 workspace 相对路径，路径逃逸被拒。

### 阶段 2：六个隔离环境逐个装

`operon_environments_prepare(names=[...])` 依次：`openmm81`、`boltz`、`antifold`、
`esmfold`、`esm3`、`colabfold`。每个都验：

- `state` 从 `missing/installing` 到 `ready`，`receipt.spec_sha256` 与当前 manifest 一致；
- import 冒烟（`import openmm` / `import boltz` / `import esm` …）；
- torch 环境看 `torch.__version__`、`torch.cuda.is_available()`、`torch.version.cuda`；
- `pip check` 无冲突；`bin/*` 的 shebang 不是 `.staging-*`；
- 记录体积与文件数。

已知历史坑：`--only-binary=:all:` 会把只有 sdist 的 `antlr4-python3-runtime==4.9.3`
判成无解（先单独装它再装其余）；venv 改名后要批改 `bin/*` shebang；共享 worker 需要
`pydantic`/`jsonschema` 才能加载 Reader schema。

### 阶段 3：路线端到端（本地）

至少覆盖四类，每类记 job id 与产物：

1. **序列面板**：`FastaReader -> sequence_liability_scan` / `antibody_developability`；
2. **结构类**：`PdbReader -> structure_interface_core` / `interface_hotspots`；
3. **OpenMM**：`structure_openmm_energy`（应走 OpenCL）、`structure_openmm_md_stability`、
   `structure_openmm_md_rmsf`（double 精度、`select_platform`）；
4. **深度学习**：`colabfold_predict`、`esmfold_predict`、`esm3_secondary_structure`、
   `antifold_score`、`boltz_complex_confidence`（GPU 优先）。

同时验证：GPU 分配（`CUDA_VISIBLE_DEVICES` 与 `OPERON_CPU_LIMIT` 出现在作业环境）、
并发（内存预算下串行是正常的）、失败重试与取消。

### 阶段 4：远程（srv）

1. 连接：`operon_remote_ensure(profile_id=...)`；若报“服务端代码或算子库与桌面端不一致”，
   说明远端库 sha 与本地不同，直接 `operon_remote_install(force=True)`。
2. 升级后核对 `build`、库 `main-v0.1.2x`、`replacement_required=false`。
3. 远端环境：`operon_environments_prepare(names=["boltz","openmm81"], profile_id=...)`，
   确认 CUDA torch 与 OpenCL 可用。
4. 远端路线：结构 + 能量各一条，产物用 `operon_download_result` 取回并比对哈希。
5. 记录远端 `setup-*.log` 的关键行与耗时。

### 阶段 5：UI 交互（无头 CDP 驱动真实 UI）

- 左栏徽标随**本机**库增删变化（装 fork1 → +1，删 → −1）；
- 来源下拉切到离线服务器时显示该源与“离线”，不把两边的库并集；
- 圆圈按钮点击只 toast“已是最新/已更新”，不打开服务器设置；
- 路线库导入后出现在包列表，卸载整包会同时删 route 记录、参数、执行文件；
- 运行状态面板（本任务重做）每个状态都有正确文案与操作。

### 阶段 6：故障注入

- 安装中断（杀掉 pip / 断网）后 `state` 在 900 s 无进展时变 `failed`，可 `force` 重装；
- 删除算子库后重启，基础库能自动补回；
- 强制升级重复点击只允许一个部署（`deploy.lock`）；
- 远端输入文件在作业结束后被回收，重复提交要先重传（这是设计，不是 bug）。

---

## 5. 运行状态 UI 重做（`frontend/src/RuntimeStatusPanel.tsx`）

现状：一列文本 + 少量按钮，信息密度低、状态不显眼、操作入口散。目标：

1. **头部摘要条**：`6 个环境 · 4 ready · 1 missing · 1 installing`，加“全部准备/刷新”按钮。
2. **卡片网格**（2–3 列，随宽度自适应），每张：
   - 环境名 + 用途一句话（来自 `environments.json` 的 `notes`）；
   - 状态 chip：`ready`（绿）/`missing`（灰）/`stale`（黄）/`installing`（蓝，带进度）/`failed`（红）；
   - 关键事实：Python 版本、体积、被哪些算子使用（`used_by` 前 3 个 + 计数）；
   - 操作：准备 / 修复 / 查看日志 / 取消（安装中才显示）。
3. **进行中操作区**：job id、阶段、已用时间、可取消；完成后自动消失。
4. **日志抽屉**：点开显示 `operon_environments` 返回的操作日志尾部，不跳页。
5. 视觉与现有设计语言一致（复用 `workspace.css` 的变量与间距，卡片 12px 圆角、
   1px 边线、hover 提亮），支持暗色（`prefers-color-scheme`），不引入新依赖。
6. 中英文案同步（`frontend/src/i18n/{zh-CN,en}.json`），空态/错误态都要有文案。
7. 单测：状态映射、操作按钮可用性、进度渲染；`npx vitest run` 全绿。

数据源就是现成的 `/api/environments`（`src/web/environment_api.py`），需要什么字段先在
后端补齐（例如 `used_by` 列表、`size_bytes`、`updated_at`），不要在前端猜。

---

## 6. 新功能：资源/权重“外链”（不拷贝）

### 6.1 需求

资源页可以把**别处已有的目录或文件**接到 Operon 的资源根，使算子/工具把它当成
“已下载”。典型：srv 上 `/public/home/lihj/operon-resources/alphafold2/params`、
`colabfold` 的 `uniref30`/`envdb`、`boltz` 的 `boltz1_conf.ckpt`。要求：

- 不复制字节（几十 GB～几百 GB）；
- 链接后 `operon_resources` 显示 `present/ready`，且 `resolve_root()` 能找到；
- 记录“这是链接、源在哪、何时建的”，可撤销；
- 本机与远端都能做（远端必须在服务器上建链接）。

### 6.2 设计

- 资源根固定：`~/.local/share/operon/resources/<id>`（Linux/macOS）或
  `%USERPROFILE%\.local\share\operon\resources\<id>`（Windows），以
  `resources.json` 的 `roots[0]` 为准，不要另造目录。
- **目录**：Windows 用 **junction**（`cmd /c mklink /J <target> <source>`，无需管理员、
  可跨卷）；POSIX 用 `os.symlink(source, target, target_is_directory=True)`。
- **单文件**：同卷优先 **hardlink**（`os.link`），跨卷退化为 symlink；Windows 上
  symlink 需要开发者模式/管理员，失败就明确报错，不要偷偷复制。
- 幂等：目标已存在且已指向同一源 → 返回 `already_linked`；指向别的源 → 409，除非 `replace=true`。
- 安全：源必须在允许的根内（默认允许 `/public/home/lihj/operon-resources`、
  `~/.cache/*`，可由 `resources.json` 的 `link_roots` 扩展）；禁止把资源根自身或其子目录
  链接进来；拒绝相对路径与 `..`；链接后做一次“穿透读”（`open(link/known_file)`）校验。
- 记账：写 `receipt-<id>.json`（`kind: "linked"`、`source`、`mode`、`created_at`、
  `probe` 的相对路径与大小），`operon_resources` 据此显示 `linked` 而不是 `downloaded`。
- 远端执行：MCP/HTTP 用 `execution.target` 决定在哪台机器上建链接；远端路径必须存在，
  返回的 `source/target` 是服务器视角。

### 6.3 接口与界面

- HTTP：`POST /api/v1/large-resources/{name}/link`（`{source, replace}`）、
  `DELETE /api/v1/large-resources/{name}/link`、`GET` 列表里带 `linked/source`。
- MCP：`operon_resource_link(name, source, profile_id=None, replace=False)`、
  `operon_resource_unlink(name, profile_id=None)`。
- 前端资源页：每行增加“链接外部…”按钮，弹窗填源路径（默认给出示例）、模式（自动/强制
  链接）、显示校验结果；已链接的行显示“链接自 <source>”与“断开链接”。
- 库侧 `resources.json` 增加可选 `link_roots` 和每个资源的 `expected_files`（用于链接后
  校验），不改已有 `downloads` 语义。

### 6.4 验收

1. 在 srv 上把 `alphafold2/params` 链进资源根 → `colabfold`/`openfold` 能直接用；
   断开后回到 `missing`。
2. 本机把一个已有权重目录链进 `~/.local/share/operon/resources/boltz` →
   `boltz_complex_confidence` 不再下载、直接跑通。
3. 链接不产生字节复制（对比前后磁盘占用）。
4. 撤销链接只删链接本体，不动源目录（用 inode/目录哈希核对）。

---

## 7. 已知坑（每条都踩过）

- `desktop_server.py` 依赖 stdin 存活；后台启动必须持有 `stdin=PIPE`。
- PowerShell：`Invoke-RestMethod` 解析 `/api/bootstrap` 会因重复键报错；`Set-Content
  -Encoding utf8` 写 `.sh` 带 BOM 会让首行 `cd`/`set` 失败；native 程序 stderr 会触发
  `NativeCommandError` 让退出码变 1（安装器“假失败”）。
- 多行中文 Markdown 一律先写到 `D:\` 再 `cat >>`/`cp` 进 WSL 仓库，**不要用 here-doc**
  （反引号、`$`、`\` 都会被 PowerShell 吃掉，曾写坏文档）。
- `\\wsl.localhost\...` 的 UNC 路径用 write/edit 改**已存在**文件可能报
  `GetFileSecurityW EIO`；新文件或走 WSL `mv`/`cp` 更稳。
- 路径前缀 `\\?\`：启动环境解释器前必须去掉，否则 `sys.prefix` 带前缀，`_openmm` 找不到 DLL。
- 版本号要改 6 处：`pyproject.toml`、`operon/__init__.py`、`frontend/package.json`、
  `frontend/package-lock.json`（2 处）、`desktop/OperonStudio.csproj`、`installer/OperonSetup.csproj`。
- 打包：`package_release.py --output` 是目录且不能已存在同名产物；payload 审计会拒绝
  文档里的开发者路径；`build_runtime.py` 要用 builder venv（含 `packaging`）；
  `build_desktop.ps1` 需要 `DOTNET_ROOT` 且在 PATH。
- 发布：先有 tag 再 `publish_release.py`；`--target` 必须是分支名；`publish` 子命令的
  全局参数写在子命令前；**库 release 必须 `make_latest=false`**，`latest` 只由应用 release 更新。
- WSL 根盘很紧（几百 MB～几 GB 浮动），大文件一律放 `D:`。

---

## 8. SSH / VPN 恢复

1. 先试直连：`ssh lihj@172.22.148.93`（或 `Test-NetConnection 172.22.148.93 -Port 22`）。
2. 失败时先确认本机网络与 WFP 隧道：`wfp_status`；必要时 `wfp_restart`（首次会弹一次 UAC
   注册计划任务，之后免授权），再重试 `ssh srv`。
3. 仍失败时试 `srv` 别名与 `172.22.148.1` 网关；记录失败时间与现象，不要连续重试几十次。
4. 远端可达后先跑一次 `operon_remote_status`，再决定 `ensure` 还是 `install(force=True)`。

---

## 9. 交付节奏

- 修完一批（尤其 UI 与资源外链）就出 **5.4.9**；如果改动跨到“新功能+接口变更”，用 **5.5.0**。
- 每次发行：四资产（Setup / Server / wheel / SHA256SUMS）进 `D:\download`，写
  `docs/releases/operon-5.4.9.md`（或 5.5.0），提交、tag、HTTP/1.1 推送、发布 latest。
- 发行前跑：`pytest`（后端聚焦 + 新增用例）、`npx vitest run`（前端全量）、`tsc -b`、
  payload 审计、97 项 native installer checks。
- 装机终验由用户做；我只给路径、哈希与证据。

## 10. 新对话第一小时建议

1. 读本文 + `docs/releases/operon-5.4.8.md` + `docs/design/route-collections.md`。
2. 核对第 2 节坐标；把 MCP 配置指到一个**新装**的 5.4.8 测试实例。
3. 先跑阶段 0/1（安装 + MCP 工具面），把失败项记进 test report。
4. 再按阶段 2→6 推进；UI 与资源外链可以在等环境安装时并行做。
5. 每修一个 bug，补一条回归测试；每完成一阶段，更新 test report 并提交。

---

## 11. 提交与下载一律走 srv 代理（硬要求）

这台机器（Windows 与 WSL 两侧）到 `github.com:443` 直连会超时或被 reset，`api.github.com`
在 WSL 里可达但不足以完成上传。**所有对 GitHub 的提交、发布、资产上传/下载都必须走 srv
代理**，不要直连。srv：`lihj@172.22.148.93`，代理服务在 srv 上监听 `127.0.0.1:18080`。

### 11.1 建立隧道

```bash
# Windows 侧开隧道（保持后台运行）
ssh -N -L 18080:127.0.0.1:18080 lihj@172.22.148.93
# 校验
curl -x http://127.0.0.1:18080 -sS -o /dev/null -w '%{http_code}\n' https://api.github.com/
```

代理是否可用也可以先看 `scripts/release_proxy/` 的默认配置（`lovegavin@127.0.0.1:18080`）。
隧道断了先 `wfp_status`/`wfp_restart`，再重连 `ssh srv`。

### 11.2 提交（git push）

优先用代理直推，令牌从文件读，**不要内联进 PowerShell**（`$`、引号会被吞）：

```bash
cd /home/gavin/Operon-540
TOK=$(cat "/mnt/c/Users/梦天曦/.operon/gh_token.txt")
https_proxy=http://127.0.0.1:18080 http_proxy=http://127.0.0.1:18080 \
  git -c http.version=HTTP/1.1 push \
  "https://x-access-token:$TOK@github.com/lovegavin/Operon.git" \
  release/5.4.0:release/5.4.0
```

代理仍失败时走 **srv 中继**（已验证可行的兜底）：

```bash
git bundle create /tmp/repo.bundle release/5.4.0
scp /tmp/repo.bundle lihj@172.22.148.93:/tmp/
ssh lihj@172.22.148.93 'cd /tmp && git clone --bare repo.bundle repo.git 2>/dev/null || git -C repo.git fetch /tmp/repo.bundle "+refs/heads/*:refs/heads/*"'
# 在 srv 上推（srv 到 github.com 可达）
ssh lihj@172.22.148.93 'cd /tmp/repo.git && git push --force "https://x-access-token:<TOKEN>@github.com/lovegavin/Operon.git" refs/heads/release/5.4.0'
```

### 11.3 发布与下载

- 发布：`scripts/release_proxy/publish_release.py --token-file /tmp/op_token --direct
  publish --tag vX.Y.Z ...`，脚本本身走代理；不要用直连 curl 上传资产。
- 大资产（Setup 约 430 MB、Server、wheel）先在本机生成，再用 `scp` 经 srv 中转；
  从 GitHub 拉取历史资产同样用 `curl -x http://127.0.0.1:18080` 或 srv 中继。
- `D:\download` 只是本地交付目录，**不是**“直连下载”的入口；给用户的哈希要来自本地生成物，
  并与 release API（经代理）的 digest 对齐后再报。
- 令牌只放在 `C:\Users\梦天曦\.operon\gh_token.txt` 或 `/tmp/op_token`（srv 侧），
  不要写进仓库、日志或对话。

### 11.4 常见失败

| 现象 | 处理 |
|---|---|
| `Could not resolve host: github.com` / 超时 | 隧道没起，重开 `ssh -N -L 18080:...` |
| `Authentication failed` | 令牌文件被换行/截断，`tr -d '\r\n'`；或改用 11.2 的 srv 中继 |
| `GnuTLS recv error (-110)` | 加 `-c http.version=HTTP/1.1` 并重试；仍失败走中继 |
| API 403（srv 上） | srv 到 `api.github.com` 返回 403 属已知，改用本机经代理调 API |
| 上传中断 | 先看代理是否存活，再重跑 `publish_release.py`（按 tag 覆盖/续传） |

### 11.5 两条实测补充

- **srv 中继是已验证的兜底**，但 srv 上的 git 很旧：不要用 `git -C`，也不要 `git init -q`；
  正确写法是在远端命令里 `cd /tmp && git init --bare 540.git && cd 540.git &&
  git fetch /tmp/540.bundle '+refs/heads/*:refs/heads/*'`，再 `git push --force <url> refs/heads/release/5.4.0`。
- **推送输出会回显带 token 的 URL**（`remote: To https://x-access-token:...`）。汇报、日志、
  截图里都不要整段贴出该输出；需要贴就先把 token 段替换成 `<TOKEN>`。
