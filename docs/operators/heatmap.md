# Heatmap (`heatmap`)

**Category:** 可视化  
**Entry point:** `src.task.step.steps.heatmap:HeatmapStep`  
**Source:** [`library/seed/src/task/step/steps/heatmap.py`](../../library/seed/src/task/step/steps/heatmap.py) (322 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

矩阵热图与层次聚类

> Heatmap of a 2D form. Renders the matrix as an image with one cell per position. Rows and columns can be reordered by hierarchical clustering, and rows can be standardized before plotting. Row selection ------------- select="variance" pick the top ``top_n`` rows by variance (default) select="label" pick the rows named in ``labels`` select="all" keep all rows Standardization --------------- standardize="row" z-score each row (mean 0, std 1) standardize="col" z-score each column standardize="none" no transformation (default) Missing values are shown as the ``nan_color``. Params: dim : feature…

关键符号：

- `class HeatmapStep (line 51)`

协议：v3 / revision `3.7`；输出参数 `None`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(dim, other_dim), info=(—)
- 输出: mode=none, schema={}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `dim` | `feature` | 分析维度 |
| `other_dim` | `sample` | 样本维度 |
| `select` | `variance` | 特征选择; choices: variance, label, all |
| `labels` | `` | 特征标签 |
| `standardize` | `none` | 标准化; choices: none, row, col |
| `filename` | `` | 图片文件名 |
| `title` | `` | 图标题 |
| `cmap` | `RdBu_r` | 配色 |
| `nan_color` | `#DDDDDD` | 缺失值颜色 |
| `figsize` | `` | 画布尺寸 [宽, 高] |
| `top_n` | `50` | 最多特征数; min 1 |
| `cluster_rows` | `True` | 聚类行 |
| `cluster_cols` | `True` | 聚类列 |
| `show_row_labels` | `False` | 显示行标签 |
| `show_col_labels` | `True` | 显示列标签 |
| `figure_width_mm` | `` | Figure width (mm) |
| `figure_height_mm` | `` | Figure height (mm) |
| `figure_dpi` | `300` | Figure resolution (DPI); min 72 |
| `figure_font_size` | `8` | Figure font size (pt) |

## 2. 用途与解释

Heatmap of a 2D form.

Renders the matrix as an image with one cell per position. Rows and
columns can be reordered by hierarchical clustering, and rows can be
standardized before plotting.

Row selection
-------------
select="variance"   pick the top ``top_n`` rows by variance
(default)
select="label"      pick the rows named in ``labels``
select="all"        keep all rows

Standardization
---------------
standardize="row"   z-score each row (mean 0, std 1)
standardize="col"   z-score each column
standardize="none"  no transformation (default)

Missing values are shown as the ``nan_color``.

Params:
dim          : feature dim (default "feature")
other_dim    : sample dim (default "sample")
select       : "variance" | "label" | "all"
top_n        : number of rows when select="variance" (default 50)
labels       : list of row labels when select="label"
standardize  : "row" | "col" | "none

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_figure_contract.py,test_heatmap_publication_layout.py,test_hic_real.py,test_history_results.py,test_report_contracts_sop.py,test_upstream_operators.py |
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
grep '^heatmap,' verification/coverage-8.0.1/operator_coverage.csv
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
