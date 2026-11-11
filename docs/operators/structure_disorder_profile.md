# Structure disorder profile (`structure_disorder_profile`)

**Category:** Structure  
**Entry point:** `src.task.step.steps.structure_disorder_profile:StructureDisorderProfileStep`  
**Source:** [`library/seed/src/task/step/steps/structure_disorder_profile.py`](../../library/seed/src/task/step/steps/structure_disorder_profile.py) (223 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Report one row per residue with the mean B-factor, its per-chain z-score, the number of unmodelled residues that follow it, and a combined disorder

> Per-residue structural disorder profile from B-factors and chain gaps. Predicted and experimental structures both expose flexibility through the B-factor column, and unmodelled stretches show up as numbering gaps. The operator combines both signals into a single per-residue disorder score so a downstream filter can drop or flag flexible regions without another

关键符号：

- `def residue_table() (line 25)`
- `def disorder_rows() (line 65)`
- `class StructureDisorderProfileStep (line 99)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(atom_dim, field_dim), info=(encoders, missing_code)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `atom_dim` | `atom` | 原子维度 |
| `field_dim` | `field` | 字段维度 |
| `residue_dim` | `residue` | 残基维度 |
| `z_clip` | `3.0` | Z 截断; max 10 |
| `output` | `disorder` | 输出槽 |

## 2. 用途与解释

Per-residue structural disorder profile from B-factors and chain gaps.

Predicted and experimental structures both expose flexibility through the
B-factor column, and unmodelled stretches show up as numbering gaps.  The
operator combines both signals into a single per-residue disorder score so a
downstream filter can drop or flag flexible regions without another parser.

Flag flexible residues from B-factors and unmodelled chain gaps.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension272.py |
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
grep '^structure_disorder_profile,' verification/coverage-8.0.1/operator_coverage.csv
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
