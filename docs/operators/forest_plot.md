# Forest plot (`forest_plot`)

**Category:** 可视化  
**Entry point:** `src.task.step.steps.forest_plot:ForestPlotStep`  
**Source:** [`library/seed/src/task/step/steps/forest_plot.py`](../../library/seed/src/task/step/steps/forest_plot.py) (297 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

HR

> Forest plot of hazard ratios from a Cox regression result. Input is the 2D form produced by ``cox_regression``: one row per covariate, one column per statistic. The operator draws a horizontal forest plot with one line per covariate, showing the point estimate of HR and its 95% confidence interval. The reference line is HR = 1 (log scale). Covariates whose CI does not cross the reference line are highlighted. Params: dim : covariate dim (default "covariate") stat_dim : statistic dim (default "statistic") hr_label : column with HR (default "HR") low_label : column with lower CI (default…

关键符号：

- `class ForestPlotStep (line 39)`

协议：v3 / revision `3.7`；输出参数 `None`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(dim, stat_dim), info=(—)
- 输出: mode=none, schema={}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `dim` | `covariate` | 分析维度 |
| `stat_dim` | `statistic` | 统计量维度 |
| `hr_label` | `HR` | HR 字段 |
| `low_label` | `CI_low` | CI 下界字段 |
| `high_label` | `CI_high` | CI 上界字段 |
| `p_label` | `P` | P / Q 字段 |
| `filename` | `` | 图片文件名 |
| `title` | `` | 图标题 |
| `xlabel` | `Hazard ratio (95% CI)` | X 轴标题 |
| `xlim` | `` | X 轴范围 |
| `color_sig` | `#D62728` | color_sig |
| `color_ns` | `#4C72B0` | color_ns |
| `sort_by` | `input` | 排序; choices: input, hr, p |
| `log_scale` | `True` | Log 坐标 |
| `figure_width_mm` | `` | Figure width (mm) |
| `figure_height_mm` | `` | Figure height (mm) |
| `figure_dpi` | `300` | Figure resolution (DPI); min 72 |
| `figure_font_size` | `8` | Figure font size (pt) |

## 2. 用途与解释

Forest plot of hazard ratios from a Cox regression result.

Input is the 2D form produced by ``cox_regression``: one row per
covariate, one column per statistic. The operator draws a horizontal
forest plot with one line per covariate, showing the point estimate
of HR and its 95% confidence interval.

The reference line is HR = 1 (log scale). Covariates whose CI does
not cross the reference line are highlighted.

Params:
dim         : covariate dim (default "covariate")
stat_dim    : statistic dim (default "statistic")
hr_label    : column with HR (default "HR")
low_label   : column with lower CI (default "CI_low")
high_label  : column with upper CI (default "CI_high")
p_label     : column with p-value (default "P")
filename    : output file name (required)
title       : optional plot title
xlabel      : optional x-label (default "Hazard ratio (95% CI)")
xlim        : optional [x_min, x_m

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
grep '^forest_plot,' verification/coverage-8.0.1/operator_coverage.csv
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
