# 缺失值填补 (`impute`)

**Category:** 数据整理  
**Entry point:** `src.task.step.steps.impute:ImputeStep`  
**Source:** [`library/seed/src/task/step/steps/impute.py`](../../library/seed/src/task/step/steps/impute.py) (247 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

以 Min、Median 或 Mean

> Impute missing values in a form. Fills missing cells using a simple strategy. Common in proteomics and metabolomics, where missing values are frequent (low-abundance features fall below the detection limit). Methods ------- min replace every missing cell with (global minimum * ``min_scale``). This is the Perseus "replace by minimum" strategy. median replace each missing cell with the median of its feature, computed over all other axes. mean replace each missing cell with the mean of its feature, computed over all other axes. The ``dim`` parameter names the feature axis. For ``median`` and…

关键符号：

- `class ImputeStep (line 51)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=?, numeric=True, dims=(dim), info=(—)
- 输出: mode=transform, schema={}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `method` | `` | 方法; choices: min, median, mean |
| `dim` | `` | 分析维度 |
| `min_scale` | `1.0` | 最小值倍率; min 0 |

## 2. 用途与解释

Impute missing values in a form.

Fills missing cells using a simple strategy. Common in proteomics
and metabolomics, where missing values are frequent (low-abundance
features fall below the detection limit).

Methods
-------
min     replace every missing cell with (global minimum *
``min_scale``). This is the Perseus "replace by minimum"
strategy.
median  replace each missing cell with the median of its feature,
computed over all other axes.
mean    replace each missing cell with the mean of its feature,
computed over all other axes.

The ``dim`` parameter names the feature axis. For ``median`` and
``mean``, the statistic is computed over every axis except ``dim``.
For ``min``, the statistic is the global minimum over the whole
matrix.

The operator works on any dimensionality >= 1. ``median`` and
``mean`` require at least one axis besides ``dim`` to aggregate
over; for 1D input, use ``

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
grep '^impute,' verification/coverage-8.0.1/operator_coverage.csv
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
