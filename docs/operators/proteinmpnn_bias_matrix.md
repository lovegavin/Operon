# ProteinMPNN bias matrix (`proteinmpnn_bias_matrix`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.proteinmpnn_bias_matrix:ProteinmpnnBiasMatrixStep`  
**Source:** [`library/seed/src/task/step/steps/proteinmpnn_bias_matrix.py`](../../library/seed/src/task/step/steps/proteinmpnn_bias_matrix.py) (297 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Build a per-residue amino-acid bias matrix for the official ProteinMPNN runner and return the designs it produces. Selected positions are pushed towards the favor residues and away from the avoid

> Per-residue amino-acid bias design with the official ProteinMPNN

关键符号：

- `def bias_matrix() (line 41)`
- `def bias_payload() (line 71)`
- `def run_bias_designer() (line 101)`
- `class ProteinmpnnBiasMatrixStep (line 166)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `structure_path` | `` | 结构文件 |
| `positions` | `` | 偏置位点 |
| `chains` | `` | 链 |
| `favor` | `WYFH` | 偏好氨基酸 |
| `avoid` | `` | 回避氨基酸 |
| `strength` | `1.0` | 偏置强度; min 0.01; max 100.0 |
| `num_seq_per_target` | `8` | 每目标序列数; min 1; max 256 |
| `sampling_temp` | `0.1` | 采样温度 |
| `seed` | `1` | 随机种子; min 0; max 100000 |
| `model_name` | `v_48_020` | 模型; choices: v_48_002, v_48_010, v_48_020, v_48_030 |
| `device` | `cpu` | 设备; choices: cpu, cuda |
| `proteinmpnn_path` | `` | ProteinMPNN 目录 |
| `weights_path` | `` | 权重目录 |
| `python_executable` | `` | Python 解释器 |
| `timeout_seconds` | `1800` | 超时; min 30; max 86400 |
| `design_dim` | `design` | 设计维度 |
| `output` | `designs` | 输出参数 |

## 2. 用途与解释

Per-residue amino-acid bias design with the official ProteinMPNN runner.

Bias selected positions towards (or away from) amino acids.

## 3. 正确性依据

**结论：B 级。** 服务器真实运行通过（161.3389 s），1 个步骤产物，首个 sha256 a38fd213846ac975…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension264.py |
| L3 真实执行 | EXECUTED_SRV | srv:/public/home/lihj/operon715/cov_mpnn/proteinmpnn_bias_matrix/output/run_summary.json |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

服务器执行细节：

- 状态：complete，总耗时 161.3389 s，步骤 1。
- 路线：`/public/home/lihj/operon715/cov_mpnn/proteinmpnn_bias_matrix`；run_id `20261110T140044-e19b9b2b8db3`。

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
grep '^proteinmpnn_bias_matrix,' verification/coverage-8.0.1/operator_coverage.csv
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
