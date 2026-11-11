# Composition barplot (`barplot`)

**Category:** 可视化  
**Entry point:** `src.task.step.steps.barplot:BarplotStep`  
**Source:** [`library/seed/src/task/step/steps/barplot.py`](../../library/seed/src/task/step/steps/barplot.py) (315 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Stacked bar plot of a matrix along one

> Stacked bar plot of a matrix along one axis. Input is a 2D form. One axis is the "composition" axis (features that will be stacked) and the other is the "sample" axis (bars). For each sample, one bar is drawn, and the features are stacked in their order along the composition axis. This is the standard visualization for compositional data: relative abundance of taxa per sample, cell-type fractions per sample, isoform fractions, etc. Layout ------ input dims: [<composition_dim>, <sample_dim>] (any orientation) output : a barplot image Feature selection ----------------- The operator can show…

关键符号：

- `class BarplotStep (line 59)`

协议：v3 / revision `3.7`；输出参数 `None`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(dim, sample_dim), info=(—)
- 输出: mode=report, schema={}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `dim` | `` | — |
| `sample_dim` | `` | — |
| `filename` | `` | — |
| `top_n` | `20` | — |
| `other_label` | `Other` | — |
| `normalize` | `True` | — |
| `title` | `` | — |
| `xlabel` | `` | — |
| `ylabel` | `` | — |
| `cmap` | `tab20` | — |
| `figsize` | `` | — |
| `legend` | `True` | — |
| `legend_ncol` | `3` | min 1 |
| `rotate_labels` | `True` | — |
| `figure_width_mm` | `` | Figure width (mm) |
| `figure_height_mm` | `` | Figure height (mm) |
| `figure_dpi` | `300` | Figure resolution (DPI); min 72 |
| `figure_font_size` | `8` | Figure font size (pt) |

## 2. 用途与解释

Stacked bar plot of a matrix along one axis.

Input is a 2D form. One axis is the "composition" axis (features
that will be stacked) and the other is the "sample" axis (bars).
For each sample, one bar is drawn, and the features are stacked in
their order along the composition axis.

This is the standard visualization for compositional data:
relative abundance of taxa per sample, cell-type fractions per
sample, isoform fractions, etc.

Layout
------
input  dims: [<composition_dim>, <sample_dim>]  (any orientation)
output      : a barplot image

Feature selection
-----------------
The operator can show only the top N most abundant features. The
remaining features are summed into a single "Other" category.

Normalization
-------------
``normalize=True`` (default) divides each sample by its total, so
each bar sums to 1. This is the correct default for compositional
data. Set to False to plot

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_report_contracts_sop.py |
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
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^barplot,' verification/coverage-8.0.1/operator_coverage.csv
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
