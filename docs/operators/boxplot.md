# Boxplot (`boxplot`)

**Category:** 可视化  
**Entry point:** `src.task.step.steps.boxplot:BoxplotStep`  
**Source:** [`library/seed/src/task/step/steps/boxplot.py`](../../library/seed/src/task/step/steps/boxplot.py) (323 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

分组分布与散点

> Boxplot of one value column split by groups. Inputs ------ 0. Data form with a value dim (typically the observation dim) and a sample dim. 1. Metadata form with the same sample dim and a column that carries the group labels. The sample axis is aligned by label between the two forms. For each group, one box is drawn for the selected value column. Domain-agnostic. Any 2D data form + any 2D metadata form works. Params: dim : dim of the data form that holds the value column (default "feature") value_label : column label to plot (required) group_dim : sample dim shared by both forms (required)…

关键符号：

- `class BoxplotStep (line 43)`

协议：v3 / revision `3.7`；输出参数 `None`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(dim, group_dim), info=(—)
- 输入 2: ndim=2, numeric=True, dims=(group_dim), info=(—)
- 输出: mode=none, schema={}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `dim` | `feature` | 分析维度 |
| `value_label` | `` | 数值字段 |
| `group_dim` | `` | 样本维度 |
| `group_label` | `` | 分组字段 |
| `groups` | `` | 显示分组顺序 |
| `filename` | `` | 图片文件名 |
| `title` | `` | 图标题 |
| `xlabel` | `` | X 轴标题 |
| `ylabel` | `` | Y 轴标题 |
| `show_points` | `True` | 显示散点 |
| `point_size` | `4` | 点大小; min 1 |
| `point_alpha` | `0.5` | 点透明度; min 0; max 1 |
| `figure_width_mm` | `` | Figure width (mm) |
| `figure_height_mm` | `` | Figure height (mm) |
| `figure_dpi` | `300` | Figure resolution (DPI); min 72 |
| `figure_font_size` | `8` | Figure font size (pt) |

## 2. 用途与解释

Boxplot of one value column split by groups.

Inputs
------
0. Data form with a value dim (typically the observation dim) and a
sample dim.
1. Metadata form with the same sample dim and a column that carries
the group labels.

The sample axis is aligned by label between the two forms. For each
group, one box is drawn for the selected value column.

Domain-agnostic. Any 2D data form + any 2D metadata form works.

Params:
dim          : dim of the data form that holds the value column
(default "feature")
value_label  : column label to plot (required)
group_dim    : sample dim shared by both forms (required)
group_label  : column label on the metadata's other dim
(required)
groups       : optional list of group names to keep, in order
filename     : output file name (required)
title        : optional plot title
xlabel       : optional x label (default: group_label)
ylabel       : optional y

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_report_contracts_sop.py,test_upstream_operators.py |
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
grep '^boxplot,' verification/coverage-8.0.1/operator_coverage.csv
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
