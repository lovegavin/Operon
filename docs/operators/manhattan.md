# 曼哈顿图 (`manhattan`)

**Category:** 可视化  
**Entry point:** `src.task.step.steps.manhattan:ManhattanStep`  
**Source:** [`library/seed/src/task/step/steps/manhattan.py`](../../library/seed/src/task/step/steps/manhattan.py) (268 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

用染色体、位置和 P

> Manhattan plot operator. Input is a single 2D form. The operator draws a genome-wide scatter of -log10(P) against cumulative genomic position. Field locations --------------- Each field is looked up either as a data column on a named dimension or as an axis-parallel info entry. ``chrom_label`` and ``pos_label`` are looked up on ``dim``; ``p_label`` is looked up on ``p_dim`` (default: ``dim``). This lets chromosome/position come from one dimension and the P value from another. Chromosome values are kept as they appear (typically strings such as ``"22"``). They are grouped, ordered and labelled…

关键符号：

- `class ManhattanStep (line 30)`

协议：v3 / revision `3.7`；输出参数 `None`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(dim), info=(—)
- 输出: mode=report, schema={}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `dim` | `feature` | 变异维度 |
| `chrom_label` | `` | 染色体字段 |
| `pos_label` | `` | 位置字段 |
| `p_dim` | `` | 统计量维度 |
| `p_label` | `` | P 值标签 |
| `filename` | `` | 文件名 |
| `alpha` | `0.85` | Opacity; min 0; max 1 |
| `point_size` | `6` | Point size; min 0 |
| `threshold` | `` | Significance threshold |
| `title` | `` | Title |
| `figure_width_mm` | `` | Figure width (mm) |
| `figure_height_mm` | `` | Figure height (mm) |
| `figure_dpi` | `300` | Figure resolution (DPI); min 72 |
| `figure_font_size` | `8` | Figure font size (pt) |

## 2. 用途与解释

Manhattan plot operator.

Input is a single 2D form. The operator draws a genome-wide scatter
of -log10(P) against cumulative genomic position.

Field locations
---------------
Each field is looked up either as a data column on a named dimension
or as an axis-parallel info entry. ``chrom_label`` and ``pos_label``
are looked up on ``dim``; ``p_label`` is looked up on ``p_dim``
(default: ``dim``). This lets chromosome/position come from one
dimension and the P value from another.

Chromosome values are kept as they appear (typically strings such as
``"22"``). They are grouped, ordered and labelled verbatim; no
encoding is applied.

Draw a Manhattan plot.

Params:
dim         : observation dim (one point per position)
chrom_label : chromosome field on ``dim``
pos_label   : position field on ``dim``
p_label     : P-value field
p_dim       : dim carrying ``p_label`` (default: ``dim``)
filenam

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension166.py,test_hierarchical_clustering.py,test_report_contracts_sop.py |
| L3 真实执行 | ROUTE | operator_table.csv:builtin_route |
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
grep '^manhattan,' verification/coverage-8.0.1/operator_coverage.csv
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
