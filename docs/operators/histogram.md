# 直方图 (`histogram`)

**Category:** 可视化  
**Entry point:** `src.task.step.steps.histogram:HistogramStep`  
**Source:** [`library/seed/src/task/step/steps/histogram.py`](../../library/seed/src/task/step/steps/histogram.py) (143 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

查看指定数值标签的分布。

> Histogram operator. Input is a single 2D form. One dimension of the form holds the attributes (columns); the other dimension holds the observations. The operator reads one labeled column and plots its

关键符号：

- `class HistogramStep (line 20)`

协议：v3 / revision `3.7`；输出参数 `None`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(dim), info=(—)
- 输出: mode=report, schema={}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `dim` | `feature` | 数值维度 |
| `value_label` | `` | 数值标签 |
| `bins` | `40` | 分箱数量; min 1 |
| `filename` | `` | 文件名 |
| `log_y` | `False` | Log Y axis |
| `title` | `` | Title |
| `xlabel` | `` | X axis label |
| `ylabel` | `Count` | Y axis label |
| `figure_width_mm` | `` | Figure width (mm) |
| `figure_height_mm` | `` | Figure height (mm) |
| `figure_dpi` | `300` | Figure resolution (DPI); min 72 |
| `figure_font_size` | `8` | Figure font size (pt) |

## 2. 用途与解释

Histogram operator.

Input is a single 2D form. One dimension of the form holds the
attributes (columns); the other dimension holds the observations.

The operator reads one labeled column and plots its distribution.

Draw a histogram.

Params:
dim         : attribute dimension (default "feature")
value_label : column label for the values
bins        : number of bins (default 40)
filename    : output file name
title       : optional plot title
xlabel      : optional x-axis label (default: value_label)
ylabel      : optional y-axis label (default: "Count")
log_y       : use log scale on the y axis (default False)

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension154.py,test_extension332.py,test_portability.py,test_report_contracts_sop.py,test_studio.py |
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
grep '^histogram,' verification/coverage-8.0.1/operator_coverage.csv
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
