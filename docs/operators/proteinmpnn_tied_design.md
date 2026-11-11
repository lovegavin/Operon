# ProteinMPNN tied-position design (`proteinmpnn_tied_design`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.proteinmpnn_tied_design:ProteinmpnnTiedDesignStep`  
**Source:** [`library/seed/src/task/step/steps/proteinmpnn_tied_design.py`](../../library/seed/src/task/step/steps/proteinmpnn_tied_design.py) (317 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Run the official ProteinMPNN runner with a tied-positions payload so that symmetry-equivalent residues receive the same amino acid, and report the design scores together with the tied payload

> ProteinMPNN tied-position design with a shared sequence across symmetry

关键符号：

- `def parse_tied_groups() (line 31)`
- `def tied_payload() (line 85)`
- `def run_tied_designer() (line 119)`
- `class ProteinmpnnTiedDesignStep (line 205)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `structure_path` | `` | 结构路径 (PDB) |
| `tied_positions` | `` | tied 位置（如 A:1,2|B:1,2） |
| `chains` | `` | 设计链（空格分隔，留空为全部） |
| `num_seq_per_target` | `8` | 采样序列数; min 1; max 100000 |
| `sampling_temp` | `0.1` | 采样温度 |
| `seed` | `1` | 随机种子; advanced |
| `design_dim` | `design` | 设计维度名; advanced |
| `model_name` | `v_48_020` | 模型; choices: v_48_002, v_48_010, v_48_020, v_48_030; advanced |
| `device` | `cpu` | 运行设备; choices: cpu, cuda; advanced |
| `proteinmpnn_path` | `` | ProteinMPNN 仓库路径; advanced |
| `weights_path` | `` | 权重目录; advanced |
| `python_executable` | `` | Python 解释器; advanced |
| `timeout` | `1800` | 超时（秒）; min 1; max 86400; advanced |
| `output` | `designs` | 输出名称 |

## 2. 用途与解释

ProteinMPNN tied-position design with a shared sequence across symmetry mates.

Tie symmetry-equivalent positions to a shared amino acid during design.

## 3. 正确性依据

**结论：B 级。** 服务器真实运行通过（18.5208 s），1 个步骤产物，首个 sha256 7be88ec6b5c5cd4a…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension237.py |
| L3 真实执行 | EXECUTED_SRV | srv:/public/home/lihj/operon715/cov_mpnn2/proteinmpnn_tied_design/output/run_summary.json |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

服务器执行细节：

- 状态：complete，总耗时 18.5208 s，步骤 1。
- 路线：`/public/home/lihj/operon715/cov_mpnn2/proteinmpnn_tied_design`；run_id `20261110T143952-5023aabc36ff`。

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。

## 4. 限制与失败模式

Declared memory modes: full. Operon retains the existing planner, disk-backed
inputs and emergency spill behavior; full-mode operators still require their
declared working set. This generated reference has not been independently
scientifically reviewed.

## 5. 复现

```bash
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^proteinmpnn_tied_design,' verification/coverage-8.0.1/operator_coverage.csv
```

算子手册中的示例：

```text
Use the registry to discover compatible Readers and validate a complete workflow
before execution. This generated page does not claim an executable scientific
example. Add a tested example and replace this generated page with authored
guidance when extending this operator.
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
