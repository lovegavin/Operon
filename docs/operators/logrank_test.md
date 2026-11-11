# Log-rank (`logrank_test`)

**Category:** 统计分析  
**Entry point:** `src.task.step.steps.logrank_test:LogrankTestStep`  
**Source:** [`library/seed/src/task/step/steps/logrank_test.py`](../../library/seed/src/task/step/steps/logrank_test.py) (318 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

整体与两两生存差异检验

> Log-rank test on survival data grouped by a label column. Compares survival distributions across groups. Statistics are delegated to lifelines: multivariate_logrank_test overall test across all groups logrank_test pairwise test between two groups Input is a single 2D form with samples as rows and clinical variables as columns. Output form ----------- dims = ["comparison", "statistic"] labels = {comparison: {"overall": 0, "A vs B": 1, ...}, statistic: {"chi2": 0, "df": 1, "P": 2}} Params: time_label : follow-up time (required) event_label : event indicator, 1 = event, 0 = censored (required)…

关键符号：

- `class LogrankTestStep (line 43)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(—), info=(—)
- 输出: mode=logrank_test, schema={}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `time_label` | `` | 随访时间字段 |
| `event_label` | `` | 事件字段 |
| `group_label` | `` | 分组字段 |
| `group_map` | `` | 分组映射 |
| `groups` | `` | 显示分组顺序 |
| `pairwise` | `False` | 两两比较 |

## 2. 用途与解释

Log-rank test on survival data grouped by a label column.

Compares survival distributions across groups. Statistics are
delegated to lifelines:

multivariate_logrank_test   overall test across all groups
logrank_test                pairwise test between two groups

Input is a single 2D form with samples as rows and clinical
variables as columns.

Output form
-----------
dims    = ["comparison", "statistic"]
labels  = {comparison: {"overall": 0, "A vs B": 1, ...},
statistic: {"chi2": 0, "df": 1, "P": 2}}

Params:
time_label   : follow-up time (required)
event_label  : event indicator, 1 = event, 0 = censored (required)
group_label  : group assignment (required)
group_map    : optional dict {raw: display} to remap group values
groups       : optional list of group names to keep, in order
pairwise     : also run pairwise comparisons (default False,
only used when there are >= 3 groups)
out

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_upstream_operators.py |
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
grep '^logrank_test,' verification/coverage-8.0.1/operator_coverage.csv
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
