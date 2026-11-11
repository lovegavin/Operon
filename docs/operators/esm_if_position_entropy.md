# ESM-IF Position Entropy (`esm_if_position_entropy`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.esm_if_position_entropy:EsmIfPositionEntropyStep`  
**Source:** [`library/seed/src/task/step/steps/esm_if_position_entropy.py`](../../library/seed/src/task/step/steps/esm_if_position_entropy.py) (221 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Sample the official ESM-IF1 inverse-folding model for a fixed backbone and report per-position sequence entropy, native recovery and consensus

> Per-position sequence entropy from ESM-IF1 sampled

关键符号：

- `def design_counts() (line 19)`
- `def position_rows() (line 43)`
- `class EsmIfPositionEntropyStep (line 62)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(atom_dim, field_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `atom_dim` | `atom` | 原子维度 |
| `field_dim` | `field` | 字段维度 |
| `position_dim` | `position` | 位点维度; advanced |
| `chain` | `A` | 链 |
| `model_path` | `` | ESM-IF 权重路径 |
| `num_samples` | `16` | 采样数; min 2; max 256 |
| `temperature` | `0.1` | 采样温度; advanced |
| `seed` | `1` | 随机种子; min 0; advanced |
| `output` | `entropy` | 输出名称; advanced |

## 2. 用途与解释

Per-position sequence entropy from ESM-IF1 sampled designs.

Estimate per-position sequence entropy by sampling ESM-IF1 designs.

## 3. 正确性依据

**结论：B 级。** 服务器真实运行通过（1523.4424 s），1 个步骤产物，首个 sha256 6b028d9d6110d3ba…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension175.py |
| L3 真实执行 | EXECUTED_SRV | srv:/public/home/lihj/operon715/cov_ml/esm_if_position_entropy/output/run_summary.json |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

服务器执行细节：

- 状态：complete，总耗时 1523.4424 s，步骤 1。
- 路线：`/public/home/lihj/operon715/cov_ml2/esm_if_position_entropy`；run_id `20261110T143808-70cff3b27ff2`。

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
grep '^esm_if_position_entropy,' verification/coverage-8.0.1/operator_coverage.csv
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
