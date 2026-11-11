# qc_metrics (`qc_metrics`)

**Category:** Quality Control  
**Entry point:** `src.task.step.steps.qc_metrics:QcMetricsStep`  
**Source:** [`library/seed/src/task/step/steps/qc_metrics.py`](../../library/seed/src/task/step/steps/qc_metrics.py) (232 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Per-sample summary metrics along a feature

> Per-sample summary metrics along a feature axis. Input: any 2D Form with axes [feature_dim, sample_dim]. For each declared metric, a summary is computed along the feature axis, producing one value per sample. A metric may restrict itself to features whose label starts with a given prefix, and may divide its raw result by another metric declared in the same call. Metrics ------- op values and their meaning over the selected feature subset: sum sum of non-missing values mean arithmetic mean of non-missing values std population standard deviation (ddof=0) var population variance (ddof=0) min…

关键符号：

- `class QcMetricsStep (line 82)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(feature_dim, sample_dim), info=(missing_code)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `feature_dim` | `feature` | 特征维度 |
| `sample_dim` | `sample` | 样本维度 |
| `metrics` | `` | 指标 |
| `output` | `` | 输出名称 |

## 2. 用途与解释

Per-sample summary metrics along a feature axis.

Input: any 2D Form with axes [feature_dim, sample_dim].

For each declared metric, a summary is computed along the feature
axis, producing one value per sample. A metric may restrict itself
to features whose label starts with a given prefix, and may divide
its raw result by another metric declared in the same call.

Metrics
-------
op values and their meaning over the selected feature subset:
sum      sum of non-missing values
mean     arithmetic mean of non-missing values
std      population standard deviation (ddof=0)
var      population variance (ddof=0)
min      minimum of non-missing values
max      maximum of non-missing values
count    number of non-missing values
nonzero  number of non-missing and non-zero values

Missing cells are recognised from info["missing_code"]: when that
code is NaN, non-finite cells count as missing.

Out

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_core_operators_sop.py |
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
grep '^qc_metrics,' verification/coverage-8.0.1/operator_coverage.csv
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
