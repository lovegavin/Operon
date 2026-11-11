# ESM-IF Score (`esm_if_score`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.esm_if_score:EsmIfScoreStep`  
**Source:** [`library/seed/src/task/step/steps/esm_if_score.py`](../../library/seed/src/task/step/steps/esm_if_score.py) (143 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Score a protein chain with the official ESM-IF1 inverse-folding model and report the per-residue log probability of the observed sequence given the

> Score a sequence against a backbone with the official ESM-IF1

关键符号：

- `class EsmIfScoreStep (line 23)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(atom_dim, field_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `atom_dim` | `atom` | 原子维度 |
| `field_dim` | `field` | 字段维度 |
| `residue_dim` | `residue` | 残基维度; advanced |
| `chain` | `A` | 打分链 |
| `model_path` | `` | ESM-IF 权重路径 |
| `sequence` | `` | 待打分序列 |
| `output` | `residue_scores` | 输出名称; advanced |

## 2. 用途与解释

Score a sequence against a backbone with the official ESM-IF1 model.

Score every residue of a chain with the official ESM-IF1 inverse-folding model.

## 3. 正确性依据

**结论：B 级。** 服务器真实运行通过（45.4931 s），2 个步骤产物，首个 sha256 d266e10a757fa7e5…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension138.py |
| L3 真实执行 | EXECUTED_SRV | srv:/public/home/lihj/operon715/cov_ml/esm_if_score/output/run_summary.json |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

服务器执行细节：

- 状态：complete，总耗时 45.4931 s，步骤 2。
- 路线：`/public/home/lihj/operon715/cov_ml/esm_if_score`；run_id `20261110T130508-6276073f7f74`。

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
grep '^esm_if_score,' verification/coverage-8.0.1/operator_coverage.csv
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
