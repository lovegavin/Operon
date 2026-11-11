# Paratope prediction (`structure_paratope_predict`)

**Category:** Structure  
**Entry point:** `src.task.step.steps.structure_paratope_predict:StructureParatopePredictStep`  
**Source:** [`library/seed/src/task/step/steps/structure_paratope_predict.py`](../../library/seed/src/task/step/steps/structure_paratope_predict.py) (291 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Annotate the Kabat CDR spans of the binder chain(s), count antigen contacts per residue and report which CDR residues form the

> Paratope residues: CDR positions that contact the

关键符号：

- `def chain_sequences() (line 47)`
- `def residue_cdr_map() (line 69)`
- `def paratope_rows() (line 81)`
- `class StructureParatopePredictStep (line 121)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(atom_dim, field_dim), info=(encoders)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `atom_dim` | `atom` | 原子维度 |
| `field_dim` | `field` | 字段维度 |
| `binder_chains` | `` | 抗体链 |
| `target_chains` | `` | 抗原链 |
| `cutoff` | `5.0` | 接触截断; min 3.0; max 10.0 |
| `min_contacts` | `1` | 最少接触数; min 1; max 20 |
| `output` | `paratope` | 输出名 |

## 2. 用途与解释

Paratope residues: CDR positions that contact the antigen.

Report CDR residues that touch the antigen in a complex.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension257.py |
| L3 真实执行 | ROUTE | operator_table.csv:builtin_route |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | ROUTE | library/seed/routes/vhh_cdr_quantification/task.yaml |

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
grep '^structure_paratope_predict,' verification/coverage-8.0.1/operator_coverage.csv
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
