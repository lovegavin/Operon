# Operon rc7 / library 0.1.19 交接文档

日期：2026-11-15 23:52（Asia/Shanghai）
工作区：`\\wsl.localhost\Ubuntu-24.04\home\gavin\Operon`
源码分支：`library/resource-download-interface`
HEAD：`1b25b2a7 fix: load provider Readers and their parameter schemas in isolated workers`
未提交：`src/web/admission.py`（pool coordinator 的 PID 比较修复）

---

## 1. 一句话现状

本地 rc7 的完整 minibinder 设计链已经跑通：RFdiffusion → ProteinMPNN → Boltz1 GPU → 界面指标 → 可开发性；**s6 是当前最优设计（iptm 0.3676）**。远端 `licai-srv` 正在做一次强制重部署，部署日志已显示 `operon-studio 5.1.17rc7` 安装完成，但 SSH 随后连接被重置，尚未确认 `server.json` 和最终 build；远端 CUDA Boltz 环境已修好（torch 2.3.1+cu121），但还没跑远端设计链。

**没有发版、没有打 tag。** app latest 仍是 `v5.1.17`；library 0.1.19 未发布。

---

## 2. 目标与硬约束

目标：在不发行、不打 release tag 的前提下，完成 Operon 5.1.17-rc7+ 源码与 library 0.1.19+ 的平台/科学链路：

- 修复 GPU 调度、环境安装、缺失算子；
- 部署本地和 `licai-srv`；
- 仅通过 MCP 实测；
- 跑通完整 minibinder 链：RFdiffusion → ProteinMPNN → Boltz/ESMFold/ESM3 → 界面/亲和力/可开发性 → 多轮筛选；
- 重写论文并提交源代码。

硬约束：

- 不发版、不打 tag、不移动 latest；
- 科学结果必须来自真实运行，不伪造；
- MCP 为主入口；直接 worker 只作为临时诊断，不作为最终证据；
- 远端和本地都要有可复现记录。

---

## 3. 版本与目录

### 本地

- 安装：`D:\OperonTest517rc7`
- 版本目录：`D:\OperonTest517rc7\versions\5.1.17-f397f8157e17`
- 版本：app `5.1.17-rc7`
- 内置库：`library\libraries\main-v0.1.19`，1177 descriptors / 1069 operators / 108 readers
- 本地 serve：`http://127.0.0.1:60968`，pid `49276`，强制 legacy 模式（见下）
- MCP 配置：`C:\Users\梦天曦\.dsh\profiles\desktop\cordis.patch.yml`
  - 包装脚本：`D:\OperonTest517rc7\run_mcp_legacy.cmd`
  - `cwd` 指向版本目录，`OPERON_ENGINE_MODE=legacy`
  - 注意：DSH 是否已经用新包装脚本重启过 MCP 需要确认；当前可用的是 60968 的 legacy serve。

### 远端

- 主机：`lihj@172.22.148.93`，RTX 3090 24 GB，driver 530.30.02
- 管理根：`/public/home/lihj/Operon/managed-v1`
- 旧代码：`code-6576417b5956c96ee4ce`（app rc7，library main-v0.1.19）
- 新部署（进行中）：`code-5b209f21871bcb27d4df`，`env-5b209f21871bcb27d4df`
- 新 build id：`151b37f88694fe4b9dfb93a37560153fc1e756236801302fdadc4467d6cc4705`
- 部署源：`source-5b209f21871bcb27d4df.tar.gz`，7,550,022 B
- 安装日志：`/public/home/lihj/Operon/managed-v1/setup-5b209f21871bcb27d4df.log`
- 部署日志最后可见行：
  - `Successfully installed operon-studio-5.1.17rc7`
  - `No broken requirements found.`
  - 之后 SSH `Connection reset`，`server.json` 尚未确认
- 远端资源根：`/public/home/lihj/operon-resources`
- 远端 Boltz 缓存：`/public/home/lihj/operon-resources/boltz`（`boltz1_conf.ckpt` 3,595,352,714 B、`ccd.pkl` 345,859,128 B）
- 远端 Boltz 环境：`/public/home/lihj/Operon/managed-v1/environments/boltz`
  - 已从 `torch 2.6.0+cpu` 换成 **`torch 2.3.1+cu121`**，`torch.cuda.is_available() == True`
  - 安装了 `nvidia-*`/`triton` 依赖；`bin/boltz` shebang 已修成该环境的 `bin/python`
  - **强制重部署理论上不会删除 `environments/boltz`，但重连后必须复核**

---

## 4. 本地科学结果（MCP 已实测）

### 4.1 靶点

- `/public/home/lihj/target_raw.pdb`
- 单链 T，193 aa，1,536 ATOM
- 序列：
  `DYSFSCYSQLEVNGSQHSLTCAFEDPDVNTTNLEFEICGALVEVKCLNFRKLQEIYFIETKKFLLIGKSNICVKVGEKSLTCKKIDLTTIVKPEAPFDLSVVYREGANDFVVTFNTSHLQKKYVKVLMHDVAYRQEKDENKWTHVNLSSTKLTLLQRKLQPAAMYEIKVRSIPDHYFKGFWSEWSPSYYFRTP`

### 4.2 RFdiffusion

- 作业：`ssh-df1ff559c6fd474ca2d11a88f12a9bc7-req-1aecb9f3aa22a463901518cb`
- 参数：`contigs="70-90 T17-209,0"`，`num_designs=1`，`device=cuda`
- 完成 103.61 s，exit 0
- 复合物 shape `[1,1124,12]`
- PDB：`/public/home/lihj/Operon/workspace/rf_target/results/req-1aecb9f3aa22a463901518cb/artifacts/rfdiffusion/847215ec3d2b4606a0b9481498cdb8db/design_0.pdb`
- 大小 75,308 B；A 链 88 aa（binder），T 链 193 aa（target）
- 分配：1 GPU（device 0），3 CPU threads，sampled RSS 6.13 GB

### 4.3 ProteinMPNN

- 作业：`ssh-df1ff559c6fd474ca2d11a88f12a9bc7-req-ca13b35f9359edf6aaceaa30`
- 完成 30 s，shape `[8,3]`，8 条序列
- 最优为 sample 4：
  - score 1.0253，recovery 0.0568
  - `TITIKITDKLTEHWGKKQLIIELEVDAEPGTKIEIILEDEGETITVTLTAKCKKMRITLEVVDGKVKVLKCYCLETGEELTIKVKTEK`
- 后续又比较了 sample 2/6/8；**s6 最终胜出**。

### 4.4 Boltz1 复评（本地 RTX 3090）

| 设计 | iptm | 界面残基数 | 界面 pLDDT | PDB |
|---|---:|---:|---:|---|
| **s6** | **0.3675776422023773** | **83** | **69.97915662650603** | `complex_eval\s6_pred.pdb`，184,580 B |
| s4 | 0.08398166298866272 | 66 | 63.5009090909091 | 186,958 B |
| s2 | 0.07991143316030502 | 64 | 66.60203125 | 186,384 B |
| s8 | 0.06947695463895798 | 55 | 66.1190909090909 | 185,482 B |

s6 binder 序列：
`SITIEITDELTEHHGKKQLIIELTVNAAPGTTVTVIIKDNNETITVTFTAKCTNMTVTLEVVNGKVSVLSAYCNTDGKNYTIKVTVSK`

结论：**s6 明显优于其它三条**，作为 lead candidate。

### 4.5 s6 界面指标（MCP 权威结果）

- MCP 作业：`20261115T154515-8d25b89c`
- 完成 3.8 s，2/2 步
- `core` artifact：`66e46162f81f4d48a84aacf2282105fe`，shape `[63,4]`
- `mb` artifact：`9d2e8a3457d04479bc6374ce5fe33e80`，shape `[31,2]`
- 报告：`D:\OperonTest517rc7\workspace\complex_eval\s6_iface_mcp_report.json`
- 数值：
  - **63 个界面残基，37 core / 26 rim**
  - chain counts：A 33，B 30
  - core_by_side：binder 21 / target 16
  - rim_by_side：binder 12 / target 14
  - `n_nonpolymer=0`
- 注意：早前 direct worker 在同一个 PDB 上给过 55/28/27；当前以 MCP 的 63/37/26 为准。

### 4.6 s6 可开发性（MCP）

- MCP 作业：`20261115T154606-d07a7ff8`
- 完成 2.0 s
- 报告：
  - `D:\OperonTest517rc7\workspace\complex_eval\s6_developability_mcp.json`
  - `D:\OperonTest517rc7\workspace\complex_eval\s6_liabilities_mcp.json`
- 可开发性：pI **6.073171615600586**，12 项统计
- 风险位点 7 个：
  - N63 脱酰胺 **high**
  - D76 异构化 **high**
  - N41 / N54 / N79 N-糖基化 medium
  - M55 氧化 medium
  - N74 脱酰胺 medium

---

## 5. 本阶段修掉的真实问题（按根因）

### 5.1 GPU 调度没有 device IDs

- 报错：`RuntimeError: The job was granted GPU capacity but no device IDs were reserved`
- 位置：`src/web/service.py:1106 worker_environment()`
- 根因：`allocation['gpu_count']=1` 但 `gpu_devices=[]`，legacy `_start` 没有把 admission 的 GPU 列表写进 allocation。
- 补丁（仅安装副本，未提交）：
  - `<version>\src\web\service.py`
  - `<version>\runtime\python\Lib\site-packages\src\web\service.py`
  - 若无 `gpu_devices`，取 `self.admission.gpus[:gpu_count]` 或 `range(gpu_count)`。
- 为了让补丁生效必须清 `__pycache__`；安装器使用 `UNCHECKED_HASH`，旧 pyc 会继续跑旧代码。

### 5.2 Pool coordinator 把自身当外部协调者

- 报错：`Waiting for available host memory and CPU`，即使 `reserved_bytes=0`、容量 33 GB。
- 位置：`src/web/admission.py::HostAdmission.reserve`
- 根因：共享池在 `resources.json` 里写 `coordinator`，旧代码 `if state.get('coordinator'): return False` 直接拒绝所有预留。
- 第一次修 `coordinator['owner'] != self.identity` 失败，因为 `HostAdmission.identity` 只有 `{created,pid}`，而 owner 是 `{boot_id,created,host,pid,service_id}`，永远不相等。
- 最终修法（repo + 两个安装副本）：
  ```python
  coordinator = state.get('coordinator')
  owner = (coordinator or {}).get('owner') or {}
  if owner and owner.get('pid') != self.identity.get('pid'):
      return False
  ```
- 目前 `src/web/admission.py` 还未提交（git status `M`）。

### 5.3 本地 legacy 临时绕过

- 即便修了 admission，MCP 仍走 pool/coordinator；为拿到科学结果，临时把两个安装副本的 `src/web/service.py` 改成 `self._configured_engine_mode = 'legacy'`。
- 同时把 8 个卡住的 coordinator 任务移到 `C:\OperonBuild\queued_jobs`：
  `req-5d61357b3a2a4437cfdd6a53`、`req-997ca782d606c41290ff8b45`、`req-b63244594b89043935f895eb`、`req-c9b8e8eeee32bdac3bcbc422`、`req-ff928bf34f6b595590bfd748`、`req-s6dev1`、`req-s6dev2`、`req-s6iface1`。
- 之后 serve 60968（pid 49276）可直接 submit/execute，MCP 作业证明链路通。
- **这是临时诊断补丁，不在 git 中；正式修复/发版前必须清理，否则 build identity 不可复现。**

### 5.4 Reader registry 在 isolated worker 为空

- 报错：`No reader for extension '.pdb' ... Known extensions: []`
- 根因：
  - `src/reader/__init__.py` 的 `READERS = _from_packages()` 依赖 `operon.packages.bundled_entries`，在 isolated worker 里为空；
  - `operon/worker.py:43` 又设置 `OPERON_REGISTRY_MAINTENANCE=1`，进一步强制 `READERS=[]`。
- 修复（已提交 `1b25b2a7`）：
  - `_from_installed_readers()` 从 `operon_readers.readers` 扫描并实例化 `Reader` 子类；
  - 补 `extensions/requires_siblings/excludes_siblings`；
  - 读取相邻 `parameters_file` JSON 绑定 `parameters_schema`；
  - maintenance 模式改为 `_from_installed_readers()`；
  - `read_source()` 在缺少 `operon_sdk.protocol` 时跳过 `validate_parameters`。
- 已确认 boltz env 下 `len(READERS)==105`，`PdbReader.extensions==['.pdb','.ent']`。

### 5.5 isolated env 缺 pydantic/jsonschema

- 报错：`No module named pydantic` / `jsonschema`
- 处理：把 app runtime 的 `pydantic`、`pydantic_core`、`annotated_types`、`typing_extensions`、`typing_inspection`、`jsonschema`、`jsonschema_specifications`、`referencing`、`rpds`、`attrs` 复制到本地 `library\environments\boltz\Lib\site-packages`。
- 这属于临时运行环境修补，长期应在 environment spec/bootstrap 中声明。

### 5.6 Boltz launcher

- 远端 `.../environments/boltz/bin/boltz` 的 shebang 曾指向已删除的 `.staging-boltz-f323fc76/bin/python`，导致“executable not found”。
- 已修为 `#!/public/home/lihj/Operon/managed-v1/environments/boltz/bin/python`。
- 本地 `...\Scripts\boltz.exe --help` 退出 1 且无输出；`python -m boltz` 也不可用（无 `__main__`）。
- 可用入口：`D:\OperonTest517rc7\workspace\rf_boltz\boltz_cli.py`：
  ```python
  from boltz.main import cli
  if __name__ == "__main__":
      cli()
  ```
  配合 `boltz_path` 指向该 `.py`。

### 5.7 Environment receipt BOM

- `library\environments\boltz\receipt.json` 被 PowerShell 写成带 BOM，`environment_install.receipt()` 解析为空，状态一直 `stale`。
- 用 Python `utf-8-sig` 读、`utf-8` 写回后，`boltz` 变 `ready`。

### 5.8 远端 Boltz 环境原本是 CPU torch

- 远端 boltz env 原为 `torch 2.6.0+cpu`，`No supported gpu backend found`。
- 已下载并安装 `torch 2.3.1`（PyPI manylinux wheel），再补齐 `nvidia-*` 依赖；现在：
  - `torch 2.3.1+cu121`
  - `torch.version.cuda == 12.1`
  - `torch.cuda.is_available() == True`
- 远端资源缓存已有 Boltz-1 权重；Boltz-2 权重没有。

### 5.9 远端强制部署

- 原因：远端旧 build `c236...` 与本地修改后的源码不匹配；`operon_remote_ensure` 反复报 `服务端代码或算子库与桌面端不一致`。
- 已于 23:49 启动 `operon_remote_install(force=true)`：
  - build id `151b37f88694fe4b9dfb93a37560153fc1e756236801302fdadc4467d6cc4705`
  - 部署源 7,550,022 B
  - 日志已出现 `operon-studio-5.1.17rc7` 安装成功、`No broken requirements found`
  - 随后 SSH 连接被重置，`server.json` 未确认
- **当前最优先要确认的就是这次部署是否完整、server start 后 build 是否等于 `151b37...`。**

---

## 6. 未完成 / 已知阻塞

1. **远端部署收尾**
   - 无法确认 `server.json`、`code-5b209...`、`env-5b209...` 是否完整。
   - SSH 现在从本机偶发超时（`Connection timed out`）。
   - 重连后先看 `server.json` 的 `build_id` 是否 `151b37...`。

2. **远端 build identity**
   - 本次部署源码包含本地安装副本的 forced-legacy 补丁（`src/web/service.py`），因此新 build 是 `151b37...`，不是旧 `c236...`。
   - 如果后续把 forced-legacy 撤回，必须重新部署，否则 handshake 又会不一致。
   - 长期应把 legacy 改动做成受控配置，而不是改源码。

3. **远端 Boltz CUDA 未验收**
   - torch 已修好，但还没跑过远端 Boltz complex。
   - 强制重部署是否保留 `environments/boltz` 需要复核。

4. **远端 reader 修复**
   - 旧代码 `code-657...` 曾手工 scp 过 `src/reader/__init__.py`；新部署 `code-5b209...` 来自本地源码，应包含 `1b25b2a7`，需确认。

5. **Pool 正式修复未完成**
   - 本地用 legacy 绕过；admission 的 PID 修复还未在正式 pool 路径验证。
   - `src/web/admission.py` 仍未提交。

6. **多轮设计不足**
   - 目前只有一轮 RFdiffusion + 8 条 MPNN + 4 条 Boltz 复评；s6 iptm 0.3676 仍偏低。
   - 需要更多 backbone、更多 epitope、更长 MPNN sampling，再筛选。

7. **论文未重写**
   - `paper/operon_bioinformatics.md`、`paper/operon_bioinformatics_zh.md` 仍是旧稿。
   - 需要加入本轮真实设计链、s6 排名、界面/可开发性结果和限制。

8. **未提交/未清理**
   - `src/web/admission.py` 未提交。
   - 安装副本里的 forced-legacy、GPU fallback、reader 环境复制都不在 git。
   - 远端旧代码 `code-657...` 和新代码 `code-5b209...` 可能并存。

---

## 7. 建议的新对话执行顺序

1. **确认远端**
   ```bash
   ssh lihj@172.22.148.93
   ls -l /public/home/lihj/Operon/managed-v1/server.json
   python3 - <<'PY'
   import json
   d=json.load(open('/public/home/lihj/Operon/managed-v1/server.json'))
   print(d.get('version'), d.get('build',{}).get('build_id'), d.get('app_dir'))
   PY
   ```
   期望 build `151b37f88694fe4b9dfb93a37560153fc1e756236801302fdadc4467d6cc4705`。

2. **启动/连接远端**
   - 先 `operon_remote_ensure(profile_id="df1ff559c6fd474ca2d11a88f12a9bc7")`。
   - 若仍 mismatch：比较本地 `<version>` 的 `build_identity` 与远端 `server.json`；必要时再 force install，或把 forced-legacy 撤回后重部署。

3. **复核远端 Boltz CUDA**
   ```bash
   /public/home/lihj/Operon/managed-v1/environments/boltz/bin/python -c \
     "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
   ```
   期望 `2.3.1+cu121 12.1 True`。

4. **远端 Boltz 复评 s6**
   - 用 MCP `operon_submit`，`FastaReader` 读 `rf_boltz_remote/s6_complex.fa`（本地已写，299 B），`boltz_complex_confidence`：
     - `boltz_path=/public/home/lihj/Operon/managed-v1/environments/boltz/bin/boltz`
     - `cache_dir=/public/home/lihj/operon-resources/boltz`
     - `model=boltz1`
     - `device=cuda`
     - `sampling_steps=20`
     - `runtime.execution={"kind":"ssh","profile_id":"df1ff559c6fd474ca2d11a88f12a9bc7"}`
   - 若还报 reader，确认新代码 `src/reader/__init__.py` 含 `_from_installed_readers`。

5. **远端界面/可开发性**
   - 用同一个 s6 PDB 跑 `structure_interface_core` + `minibinder_interface`，与本地 63/37/26 对照。
   - 用 s6 binder FASTA 跑 `antibody_developability` + `sequence_liability_scan`。

6. **扩大设计**
   - 至少再跑 3–5 个 RFdiffusion backbone（不同 epitope/contig），每个 8–16 条 MPNN，Boltz 复评后按 iptm/界面 pLDDT/风险位点排序。
   - 目标不是“跑通”，而是把 s6 的 iptm 从 0.37 往上推。

7. **论文**
   - 把真实数据写进 `paper/operon_bioinformatics.md` 和 `_zh.md`：
     - 设计链与参数；
     - s2/s4/s6/s8 排名；
     - s6 界面 63/37/26；
     - pI 6.073 与 7 个风险位点；
     - 明确限制：单轮、Boltz1、20 steps、无实验验证。

8. **提交源码**
   - `src/web/admission.py` 的 PID 比较修复要提交。
   - 决定 forced-legacy 是否保留；若要保留，必须做成显式配置并同步 remote build；若不保留，撤回后重新部署。
   - 不要提交安装副本、临时 receipt/pyc、`C:\OperonBuild` 产物。

---

## 8. 关键证据文件

- 本地 s6 PDB：`D:\OperonTest517rc7\workspace\complex_eval\s6_pred.pdb`
- s6 界面报告：`D:\OperonTest517rc7\workspace\complex_eval\s6_iface_mcp_report.json`
- s6 可开发性：`D:\OperonTest517rc7\workspace\complex_eval\s6_developability_mcp.json`
- s6 风险位点：`D:\OperonTest517rc7\workspace\complex_eval\s6_liabilities_mcp.json`
- s2/s4/s8 PDB 同目录：`s2_pred.pdb`、s8_pred.pdb；s4 原始 186,958 B
- 远端 RFdiffusion PDB：`/public/home/lihj/Operon/workspace/rf_target/results/req-1aecb9f3aa22a463901518cb/artifacts/rfdiffusion/847215ec3d2b4606a0b9481498cdb8db/design_0.pdb`
- 远端部署日志：`/public/home/lihj/Operon/managed-v1/setup-5b209f21871bcb27d4df.log`
- 远端旧代码：`/public/home/lihj/Operon/managed-v1/code-6576417b5956c96ee4ce`
- 远端新代码：`/public/home/lihj/Operon/managed-v1/code-5b209f21871bcb27d4df`
- 本地 serve 日志：`C:\OperonBuild\serve60968d.out.log` / `.err.log`
- 本地 MCP 包装：`D:\OperonTest517rc7\run_mcp_legacy.cmd`

---

## 9. 不要重复踩的坑

1. 不要在没有确认 `server.json` build 的情况下反复 `operon_remote_ensure`；先看 build。
2. 不要直接改远端 `code-*/src` 后不做记录；它会导致下一次 handshake 失败。
3. 不要在 provider 代码里手工改 `boltz_complex_confidence.py`；`verify_code` 会做整包 `.py` 哈希，改了必报 `Implementation code hash mismatch`。
4. 不要用 `Set-Content -Encoding utf8` 写 `receipt.json`；Windows PowerShell 可能带 BOM，Python 读成空。
5. 不要用 `boltz.exe` 作为 launcher；本地用 `boltz_cli.py`，远端用 `bin/boltz`（shebang 已修）。
6. 安装器使用 `UNCHECKED_HASH`，改完安装副本必须清 `__pycache__` 并重启。
7. Pool 卡住时先看 `resources.json` 的 `coordinator.owner.pid` 和 job 的 `scheduling`；不要盲目加内存。
8. `operon_submit` 的算子参数在节点 `params` 字段，不是 `parameters`；零输入节点 `input_count: 0`。
9. 远端 Boltz-2 权重不存在，只有 Boltz-1；不要用 `model=boltz2` 除非先补权重。
10. 不要发版/打 tag，直到用户明确说可以。
