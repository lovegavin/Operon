# scale_features (`scale_features`)

**Category:** Data  
**Entry point:** `src.task.step.steps.scale_features:ScaleFeaturesStep`  
**Source:** [`library/seed/src/task/step/steps/scale_features.py`](../../library/seed/src/task/step/steps/scale_features.py) (157 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Z-score standardise a 2D Form along one

> Z-score standardisation along one axis of a 2D numeric Form. Input: any 2D Form. Missing cells are recognised from info["missing_code"]; when that code is NaN, non-finite cells count as missing. Missing cells stay missing in the output. For every position along the *other* axis, values are rescaled so that, across ``dim``, they have mean 0 and population standard deviation 1: x' = (x - mean_over_dim) / std_over_dim Mean and std are computed with NaN-aware aggregation. Positions whose std is effectively zero are shifted to 0 (the numerator is already 0 for a constant row), not turned into NaN.…

关键符号：

- `class ScaleFeaturesStep (line 51)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(dim), info=(missing_code)
- 输出: mode=transform, schema={}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `dim` | `sample` | 分析维度 |
| `max_value` | `None` | 最大值; advanced |
| `output` | `` | 输出名称 |

## 2. 用途与解释

Z-score standardisation along one axis of a 2D numeric Form.

Input: any 2D Form. Missing cells are recognised from
info["missing_code"]; when that code is NaN, non-finite cells count
as missing. Missing cells stay missing in the output.

For every position along the *other* axis, values are rescaled so
that, across ``dim``, they have mean 0 and population standard
deviation 1:

x' = (x - mean_over_dim) / std_over_dim

Mean and std are computed with NaN-aware aggregation. Positions whose
std is effectively zero are shifted to 0 (the numerator is already
0 for a constant row), not turned into NaN.

When ``max_value`` is given, the rescaled value is clipped to
[-max_value, +max_value] after standardisation.

Output: same dims and labels as the input. ``data`` is replaced;
``representation`` becomes ``"scaled"``; genotype/alphabet semantics
and encoders are cleared because the numeric value

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_core_operators_sop.py |
| L3 真实执行 | ROUTE | operator_table.csv:generated_route |
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
grep '^scale_features,' verification/coverage-8.0.1/operator_coverage.csv
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
