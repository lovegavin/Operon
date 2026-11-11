# Aggregate (`aggregate`)

**Category:** 数据整理  
**Entry point:** `src.task.step.steps.aggregate:AggregateStep`  
**Source:** [`library/seed/src/task/step/steps/aggregate.py`](../../library/seed/src/task/step/steps/aggregate.py) (334 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Aggregate positions along one axis by

> Aggregate positions along one axis by group. Two inputs share an axis (the "row" axis). The first input carries values; the second carries a group label for each position. For each group, the operator collapses all positions in that group into a single row by applying a reduction (sum, mean, median, ...). This is the natural companion of ``join``: where ``join`` attaches metadata columns to a form, ``aggregate`` reduces a form by a metadata column. Typical uses: - collapse species to genus before plotting composition - collapse cells to clusters before profiling - collapse genes to pathways…

关键符号：

- `class AggregateStep (line 66)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(dim), info=(—)
- 输入 2: ndim=2, numeric=True, dims=(dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info": {"missing_code": {"type": ["number", "null"]}, "representation": {"type": "string", "const": "aggregate"}}, "labels": {}}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `dim` | `` | — |
| `group_col` | `` | — |
| `method` | `sum` | choices: sum, mean, median, min, max, count |

## 2. 用途与解释

Aggregate positions along one axis by group.

Two inputs share an axis (the "row" axis). The first input carries
values; the second carries a group label for each position. For
each group, the operator collapses all positions in that group
into a single row by applying a reduction (sum, mean, median, ...).

This is the natural companion of ``join``: where ``join`` attaches
metadata columns to a form, ``aggregate`` reduces a form by a
metadata column. Typical uses:

- collapse species to genus before plotting composition
- collapse cells to clusters before profiling
- collapse genes to pathways before scoring
- collapse any [row, other] matrix by a [row, group] table

Layout
------
data    dims: [row_dim, other_dim]   (any two axes)
groups  dims: [row_dim, group_dim]   (same row_dim first)
output  dims: [group_dim, other_dim]

Both inputs must be 2D with ``dim`` as their first axis. To us

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_aggregate_promote.py,test_microbiome.py |
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
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^aggregate,' verification/coverage-8.0.1/operator_coverage.csv
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
