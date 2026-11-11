# RDKit Oral Bioavailability Rules (`rdkit_oral_bioavailability`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.rdkit_oral_bioavailability:RdkitOralBioavailabilityStep`  
**Source:** [`library/seed/src/task/step/steps/rdkit_oral_bioavailability.py`](../../library/seed/src/task/step/steps/rdkit_oral_bioavailability.py) (197 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Evaluate the Lipinski, Veber and Egan rule sets for oral bioavailability from SMILES and report descriptor values, violations and a combined pass

> Rule-based oral bioavailability flags from SMILES (RDKit

关键符号：

- `def bioavailability_row() (line 29)`
- `class RdkitOralBioavailabilityStep (line 81)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `smiles` | `` | SMILES 列表 |
| `mw_max` | `500.0` | 分子量上限; min 1; advanced |
| `logp_max` | `5.0` | cLogP 上限; advanced |
| `hbd_max` | `5` | 氢键供体上限; min 0; advanced |
| `hba_max` | `10` | 氢键受体上限; min 0; advanced |
| `tpsa_max` | `140.0` | Veber TPSA 上限; min 1; advanced |
| `rotatable_bonds_max` | `10` | Veber 可旋转键上限; min 0; advanced |
| `egan_tpsa_max` | `131.6` | Egan TPSA 上限; min 0; advanced |
| `egan_logp_max` | `5.88` | Egan cLogP 上限; advanced |
| `molecule_dim` | `molecule` | 分子维度; advanced |
| `output` | `bioavailability` | 输出名称; advanced |

## 2. 用途与解释

Rule-based oral bioavailability flags from SMILES (RDKit descriptors).

Flag rule-based oral bioavailability from RDKit descriptors.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension145.py,test_extension148.py |
| L3 真实执行 | ROUTE | operator_table.csv:generated_route |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。
- 注意：该算子没有独立数值 oracle， correctness 仅到“契约/测试/执行”层级。

## 4. 限制与失败模式

Declared memory modes: full. Operon retains the existing planner, disk-backed
inputs and emergency spill behavior; full-mode operators still require their
declared working set. This generated reference has not been independently
scientifically reviewed.

## 5. 复现

```bash
cd /path/to/Operon-worktree
python -m operon registry check --json
grep '^rdkit_oral_bioavailability,' verification/coverage-8.0.1/operator_coverage.csv
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
