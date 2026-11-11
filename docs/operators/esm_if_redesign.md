# ESM-IF Partial Redesign (`esm_if_redesign`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.esm_if_redesign:EsmIfRedesignStep`  
**Source:** [`library/seed/src/task/step/steps/esm_if_redesign.py`](../../library/seed/src/task/step/steps/esm_if_redesign.py) (195 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Redesign selected positions of a protein backbone with the official ESM-IF inverse-folding model while keeping the remaining residues fixed, then score every sampled sequence under the same

> Partial redesign of a protein backbone with the official ESM-IF

关键符号：

- `def designed_recovery() (line 31)`
- `class EsmIfRedesignStep (line 39)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(atom_dim, field_dim), info=(encoders)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `atom_dim` | `atom` | 原子维度 |
| `field_dim` | `field` | 字段维度 |
| `chain` | `A` | 链 |
| `model_path` | `` | ESM-IF 权重路径 |
| `design_positions` | `` | 设计位点; advanced |
| `num_samples` | `4` | 采样数; min 1; max 16; advanced |
| `temperature` | `0.1` | 采样温度; min 0.01; max 2.0; advanced |
| `seed` | `1` | 随机种子; min 0; advanced |
| `output` | `output` | 输出名称 |

## 2. 用途与解释

Partial redesign of a protein backbone with the official ESM-IF model.

## 3. 正确性依据

**结论：B 级。** 服务器真实运行通过（121.1424 s），1 个步骤产物，首个 sha256 cc3a02610901269f…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension150.py,test_extension153.py,test_extension181.py |
| L3 真实执行 | EXECUTED_SRV | srv:/public/home/lihj/operon715/cov_ml/esm_if_redesign/output/run_summary.json |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

服务器执行细节：

- 状态：complete，总耗时 121.1424 s，步骤 1。
- 路线：`/public/home/lihj/operon715/cov_ml2/esm_if_redesign`；run_id `20261110T150337-dfd7f6ca4faa`。

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
grep '^esm_if_redesign,' verification/coverage-8.0.1/operator_coverage.csv
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
