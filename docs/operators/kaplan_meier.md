# KM (`kaplan_meier`)

**Category:** 可视化  
**Entry point:** `src.task.step.steps.kaplan_meier:KaplanMeierStep`  
**Source:** [`library/seed/src/task/step/steps/kaplan_meier.py`](../../library/seed/src/task/step/steps/kaplan_meier.py) (345 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

分组生存曲线与置信区间

> Kaplan-Meier survival curves. Input is a single 2D form with rows = samples and columns = clinical variables. The operator reads three columns, groups samples by the group column, and draws one survival curve per group. Group values can be remapped before plotting via ``group_map``. This is the standard way to collapse substages (``Stage IA``, ``Stage IIB``) into main stages (``Stage I``, ``Stage II``), or to merge any set of raw labels into a smaller set of display groups. Params: time_label : column with follow-up time (required) event_label : column with event indicator (required)…

关键符号：

- `class KaplanMeierStep (line 40)`

协议：v3 / revision `3.7`；输出参数 `None`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(—), info=(—)
- 输出: mode=none, schema={}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `time_label` | `` | 随访时间字段 |
| `event_label` | `` | 事件字段 |
| `group_label` | `` | 分组字段 |
| `group_map` | `` | 分组映射 |
| `groups` | `` | 显示分组顺序 |
| `filename` | `` | 图片文件名 |
| `title` | `` | 图标题 |
| `xlabel` | `Time` | X 轴标题 |
| `ylabel` | `Survival probability` | Y 轴标题 |
| `xlim` | `` | X 轴范围 |
| `show_censors` | `True` | 显示删失标记 |
| `show_ci` | `False` | 显示置信区间 |
| `figure_width_mm` | `` | Figure width (mm) |
| `figure_height_mm` | `` | Figure height (mm) |
| `figure_dpi` | `300` | Figure resolution (DPI); min 72 |
| `figure_font_size` | `8` | Figure font size (pt) |

## 2. 用途与解释

Kaplan-Meier survival curves.

Input is a single 2D form with rows = samples and columns = clinical
variables. The operator reads three columns, groups samples by the
group column, and draws one survival curve per group.

Group values can be remapped before plotting via ``group_map``.
This is the standard way to collapse substages (``Stage IA``,
``Stage IIB``) into main stages (``Stage I``, ``Stage II``), or to
merge any set of raw labels into a smaller set of display groups.

Params:
time_label    : column with follow-up time (required)
event_label   : column with event indicator (required)
group_label   : column with group assignment (required)
group_map     : optional dict {raw_value: display_value}. Raw
values not in the dict are kept as-is.
groups        : optional list of display group names to keep,
in output order
filename      : output file name (required)
title         : option

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_desktop_upgrade.py,test_report_contracts_sop.py,test_upstream_operators.py |
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
grep '^kaplan_meier,' verification/coverage-8.0.1/operator_coverage.csv
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
