# Axis statistics (`reduce_axis`)

**Category:** 统计分析  
**Entry point:** `src.task.step.steps.reduce_axis:ReduceAxisStep`  
**Source:** [`library/seed/src/task/step/steps/reduce_axis.py`](../../library/seed/src/task/step/steps/reduce_axis.py) (230 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Reduce one axis of a form to summary

> Reduce one axis of a form to summary statistics. For each position along ``dim``, computes one or more summary statistics over all other axes, and returns a new form in which ``dim`` is replaced by a ``"statistic"`` axis. Layout ------ input dims: [..., dim, ...] (any ndim >= 1) output dims: [..., "statistic"] (dim removed) The reduced dim is removed; every other dim keeps its original order; the new ``"statistic"`` axis is appended last. Supported statistics -------------------- sum sum of values mean mean of values std standard deviation var variance min minimum max maximum median median…

关键符号：

- `class ReduceAxisStep (line 63)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=?, numeric=True, dims=(dim), info=(—)
- 输出: mode=project, schema={}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `dim` | `` | — |
| `stats` | `` | — |

## 2. 用途与解释

Reduce one axis of a form to summary statistics.

For each position along ``dim``, computes one or more summary
statistics over all other axes, and returns a new form in which
``dim`` is replaced by a ``"statistic"`` axis.

Layout
------
input  dims: [..., dim, ...]     (any ndim >= 1)
output dims: [..., "statistic"]  (dim removed)

The reduced dim is removed; every other dim keeps its original
order; the new ``"statistic"`` axis is appended last.

Supported statistics
--------------------
sum        sum of values
mean       mean of values
std        standard deviation
var        variance
min        minimum
max        maximum
median     median
nonzero    number of non-zero values
count      number of non-missing values

Missing cells are identified via ``info["missing_code"]`` when set
and finite, otherwise via NaN. Every statistic except ``count`` and
``nonzero`` excludes missing cells;

## 3. 正确性依据

**结论：B 级。** 真实运行通过（2.02 s），导出 12 行，产物 sha256 9240075cd4515cd1…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_axis_adapters.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/reduce_axis |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 2.02 s，导出 12 行。
- 归档路线：`/tmp/cov_stats/reduce_axis`。
- 命令：`cd /path/to/Operon-worktree && python scripts/run.py /tmp/cov_stats/reduce_axis --check && python scripts/run.py /tmp/cov_stats/reduce_axis`。

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。

## 4. 限制与失败模式

Declared memory modes: full. Operon retains the existing planner, disk-backed
inputs and emergency spill behavior; full-mode operators still require their
declared working set. This generated reference has not been independently
scientifically reviewed.

## 5. 复现

```bash
cd /path/to/Operon-worktree
python -m operon registry check --json
grep '^reduce_axis,' verification/coverage-8.0.1/operator_coverage.csv
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
