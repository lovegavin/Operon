# 算子库变更总览：Library v7.0.1 → 0.1.0

- 基线：`library-v7.0.1` = `8133781c`（Studio 3.1.4 / 3.1.6 时代）
- 终点：`operon-library-main-v0.1.0` = `0b6a8a0c`（Studio 5.1.2+）
- 当前库声明：`library/release.json` → `version 0.1.0`、`minimum_application 5.0.0`
- 当前主库内容：**1066 operators / 108 Readers / 1174 descriptors / 7 packages / 79 routes**
- 额外分支：`fork1-v0.0.0`（1 package / 1 operator），独立 tag 与 release
- 版本线：`library-v7.0.1` → `library-v7.0.2 … 7.0.15` → `library-v8.0.0 … 8.0.10` → `operon-library-v0.0.0` → `0.1.0`

> 本文只讲**库侧**。应用侧见 `01-application-changes-3.1.6-to-5.1.5.md`，
> 当前架构与解耦契约见 `03-current-state-and-decoupling.md`。

## 1. 7.0.x：审计、修复与覆盖率

7.0.1 是旧审计线的最后一版：1063 算子、108 Reader、1171 描述符、78 条模板路线，目标
Studio 3.1.4/3.1.6。7.0.2 起不再以“加算子”为主，而是把审计工具链和证据做进发布物。

| 版本 | 关键内容 |
|---|---|
| 7.0.2 | 首个 L0–L5 审计工具链；修 `graph_pseudotime`、`cohens_kappa`、`fba_flux_balance`、`pedigree_inbreeding` |
| 7.0.3–7.0.4 | 继续修 L1 暴露的契约缺陷；审计归档随包发布 |
| 7.0.5 | L0 1171/1171 PASS；L1 358 PASS / 0 FAIL；L2 5/5；L3 覆盖 459/1063 |
| 7.0.6 | 覆盖统计修正（不再把 `export_results` 当算子）；生成逐算子表 |
| 7.0.7 | `aggregate` 重复维修复（`cdr_index` 提升为新维）；新增 `vhh_cdr_quantification`，79 条路线 |
| 7.0.8 | L2 13/13；零输入路线 +11；覆盖 522 |
| 7.0.9 | 40 条序列输入路线；覆盖 562 |
| 7.0.11–7.0.12 | 覆盖 653；补回被 `.gitignore` 漏掉的 `operator_table.csv` |
| 7.0.13 | 覆盖 779；修 `structure_aromatic_stacking` 重复芳香键标签 |
| 7.0.15 | 覆盖 794/1063，269 条带原因 SKIP；修 Quickstart 误带示例数据 |

这一阶段没有新增算子；价值在于：
- 证明“声明了 contracts”不等于“违反时会被拦截”，L1 负例成为固定项；
- 建立逐算子 trust sheet 与覆盖表；
- 把“缺数据/缺工具/缺权重”的 SKIP 写成可审计记录，禁止留空。

## 2. 8.0.x：原生 Operon 库与注册修复

8.0.0 要求 **Studio 3.1.9+**，去掉 legacy `biopipe` 树，bundle 只含原生
`operon/**`、`src/**`、`packages/*.whl` 和 `library.json`。算子数仍为 1063/108/1171。

| 版本 | 关键内容 |
|---|---|
| 8.0.0 | 原生 Operon；`operon_sdk` / `operon.bytecode` 取代 `biopipe_*`；1063/108/1171 |
| 8.0.1 | Studio 4.0.0 注册修复：`code_sha` 改为源码树 hash；Reader 显式消歧；`missing_code` 传播；survival 静态标签放宽 |
| 8.0.2 | 五层覆盖与 trust sheets（1063 份）；L2 补 12 项；4 个资源型 SKIP 明确记录 |
| 8.0.3 | interface 算子补 `statistic` 静态 labels；补 OpenMM/MD 依赖声明；`export_results` 去掉 `hictkpy` 硬依赖 |
| 8.0.4 | 拼接矩阵（join/aggregate 精确 `compatible`）与依赖归属审计；最低应用 4.0.7 |
| 8.0.5 | `openmm81` 独立环境（Python 3.11 + OpenMM 8.1.1 + NumPy 1.26.4 + PDBFixer 1.9） |
| 8.0.6 | `environments.json` 随 `.operon-library.zip` 分发；最低应用 4.1.0 |
| 8.0.7 | `setuptools<81` 保住 `pkg_resources`；PDBFixer 内置；openmm81 改用 `venv_shared` |
| 8.0.8 | `interface_alanine_scan` 双侧语义、QC/排除标记；`interface_mmgbsa_delta` protocol/QC |
| 8.0.9 | 上述修复的发布版；但产物 pin 不一致（库包 `a49…` vs Routes `9d8…`） |
| 8.0.10 | 用同一份 `builtin_packages.json` 重建库包与 Routes，pin 统一为 `a49cb693…` |

8.0.9 是必须记住的事故：**库包和 Routes 在不同 catalog 快照上构建**，安装后路线 pin 永远匹配不上。
8.0.10 修复了产物，但身份仍是“源码一套、wheel 一套”的双域；这也是后来彻底解耦的直接原因。

## 3. 0.0.0 / 0.1.0：独立库线

5.0.0 起库从应用仓库的内置 seed 变成独立发布物，版本从 0.0.0 重新开始。

### 3.1 契约

- 文件名：`operon-library-v<ver>.operon-library.zip`
- `library.json`：
  - `format: operon.library`
  - `bundle_format: 1`
  - `library_version`
  - `library_name`（默认 `main`）
  - `minimum_application`
  - `operator_protocol: {version: 3, revision: "3.7"}`
  - `packages[]`：`name`、`version`、`wheel`、`wheel_sha256`、`code_sha`、`entry_points`
- `SHA256SUMS` 覆盖全部成员；wheel 内带 `.dist-info/operon.json` 与 `entry_points.txt`。
- 路线集合：`operon-routes-<name>-v<ver>.zip`，`routes.json` + `routes/*.operon.zip`，每个 route 恰为
  `graph.json` / `parameters.json` / `execution.json`。

### 3.2 身份唯一

`operon_library_builder` 对每个 package 的源码做规范化哈希，得到唯一 `code_sha`，并写入：

1. `library.json` 的 package 记录；
2. wheel 内 `operon.json`；
3. 每个 route 的 `plugin_lock`。

应用只读取，不重算、不改写。builder 不 `import operon`，只依赖 `operon_sdk` 与标准库。

### 3.3 内容

| 版本 | operators | Readers | descriptors | packages | routes |
|---|---:|---:|---:|---:|---:|
| 0.0.0 | 1063 | 108 | 1171 | 7 | 79 |
| 0.1.0 | 1066 | 108 | 1174 | 7 | 79 |
| fork1 0.0.0 | 1 | 0 | 1 | 1 | 0 |

0.1.0 新增：
- `sequence_dinucleotide_frequency`
- `numeric_gini_coefficient`
- `diversity_simpson`

fork1 新增：
- `fork1_numeric_gini`（package `operon-fork1`，module `operon_fork1`）

三个新算子都有字面 definition、显式 `data_formats`、独立参数 schema、英文文档与手算 oracle。

### 3.4 发布与标签

| 产物 | tag | 说明 |
|---|---|---|
| 主库 0.0.0 | `operon-library-v0.0.0` | 首个独立库；7 包 / 1171 描述符 |
| 主库 0.1.0 | `operon-library-main-v0.1.0` | 新命名；含 3 个新算子 |
| fork1 0.0.0 | `operon-library-fork1-v0.0.0` | 共存测试库；1 个算子 |

release 资产都包含 `.operon-library.zip` + `SHA256SUMS.txt`；fork1 没有路线包。
旧 `operon-library-v0.0.0` / `v0.1.0` 资产已按新命名重新上传，tag 名保留。

## 4. 关键教训

1. **身份只能算一次**。源码、wheel、route pin 三处不一致时，应用侧无法“猜”对应关系；
   `refresh_missing` 不是发布错误的兜底。
2. **产物必须同源构建**。库包与 Routes 必须来自同一份 `builtin_packages.json`；发布门禁应比较
   三方 `code_sha`，不一致直接拒绝发布。
3. **环境是库的声明**。`resources.environment` + `environments.json` 必须随库分发；应用只负责创建与探测，
   不能回退共享解释器。
4. **审计要区分 PASS / SKIP**。缺数据、缺工具、缺权重都写原因；不能把“未测”算成“通过”。
5. **格式变更要显式拒绝**。5.0 对 8.x 直接报错，避免“装到一半失败”或静默降级。
