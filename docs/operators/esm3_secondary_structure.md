# ESM-3 secondary structure prediction (`esm3_secondary_structure`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.esm3_secondary_structure:Esm3SecondaryStructureStep`  
**Source:** [`library/seed/src/task/step/steps/esm3_secondary_structure.py`](../../library/seed/src/task/step/steps/esm3_secondary_structure.py) (191 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Predict DSSP-style secondary structure for one protein sequence with the ESM-3 secondary-structure

> esm3_secondary_structure: ESM-3 secondary-structure track

关键符号：

- `def state_code() (line 20)`
- `def clean_structure() (line 30)`
- `def ss_summary() (line 41)`
- `def load_model() (line 58)`
- `def predict_secondary_structure() (line 79)`
- `class Esm3SecondaryStructureStep (line 93)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sequence_dim, position_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sequence_dim` | `sequence` | 序列维度 |
| `position_dim` | `position` | 位点维度 |
| `model_name` | `esm3_sm_open_v1` | 模型名称 |
| `device` | `cpu` | 设备; choices: cpu, cuda |
| `num_steps` | `8` | 生成步数; min 1; max 64 |
| `report_dim` | `residue` | 输出维度 |
| `output` | `ss` | 输出参数名 |

## 2. 用途与解释

esm3_secondary_structure: ESM-3 secondary-structure track prediction.

## 3. 正确性依据

**结论：B 级。** 服务器真实运行通过（230.6143 s），1 个步骤产物，首个 sha256 002470c3c08106be…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension343.py |
| L3 真实执行 | EXECUTED_SRV | srv:/public/home/lihj/operon715/cov_ml3/esm3_secondary_structure/output/run_summary.json |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

服务器执行细节：

- 状态：complete，总耗时 230.6143 s，步骤 1。
- 路线：`/public/home/lihj/operon715/cov_ml3/esm3_secondary_structure`；run_id `20261110T134529-b1e79e9eaf16`。

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
grep '^esm3_secondary_structure,' verification/coverage-8.0.1/operator_coverage.csv
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
