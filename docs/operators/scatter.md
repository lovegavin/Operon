# 散点图 (`scatter`)

**Category:** 可视化  
**Entry point:** `src.task.step.steps.scatter:ScatterStep`  
**Source:** [`library/seed/src/task/step/steps/scatter.py`](../../library/seed/src/task/step/steps/scatter.py) (192 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

选择两个标签绘制散点图。

> Scatter plot operator. Input is a single 2D form. One dimension of the form holds the attributes (columns); the other dimension holds the observations (points). The operator reads two labeled columns as x and y, optionally a third as a color group, and writes a scatter plot to

关键符号：

- `class ScatterStep (line 22)`

协议：v3 / revision `3.7`；输出参数 `None`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(dim), info=(—)
- 输出: mode=report, schema={}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `dim` | `feature` | 坐标维度 |
| `x_label` | `` | 横坐标标签 |
| `y_label` | `` | 纵坐标标签 |
| `filename` | `` | 文件名 |
| `alpha` | `0.7` | Opacity; min 0; max 1 |
| `color_label` | `` | Color field |
| `point_size` | `8` | Point size; min 0 |
| `title` | `` | Title |
| `xlabel` | `` | X axis label |
| `ylabel` | `` | Y axis label |
| `figure_width_mm` | `` | Figure width (mm) |
| `figure_height_mm` | `` | Figure height (mm) |
| `figure_dpi` | `300` | Figure resolution (DPI); min 72 |
| `figure_font_size` | `8` | Figure font size (pt) |

## 2. 用途与解释

Scatter plot operator.

Input is a single 2D form. One dimension of the form holds the
attributes (columns); the other dimension holds the observations
(points).

The operator reads two labeled columns as x and y, optionally a third
as a color group, and writes a scatter plot to ``output/figures/``.

Draw a scatter plot.

Params:
dim         : attribute dimension (default "feature")
x_label     : column label for the x axis
y_label     : column label for the y axis
color_label : optional column label for grouping
filename    : output file name (e.g. "pca.png")
title       : optional plot title
xlabel      : optional x-axis label (default: x_label)
ylabel      : optional y-axis label (default: y_label)
point_size  : marker size (default 8)
alpha       : marker transparency (default 0.7)

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_audit_fixes.py,test_publication_figures.py,test_release_build.py,test_report_contracts_sop.py,test_service_long_paths.py |
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
grep '^scatter,' verification/coverage-8.0.1/operator_coverage.csv
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
