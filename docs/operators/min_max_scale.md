# Min-max scaling (`min_max_scale`)

**Category:** Data  
**Entry point:** `src.task.step.steps.min_max_scale:MinMaxScaleStep`  
**Source:** [`library/seed/src/task/step/steps/min_max_scale.py`](../../library/seed/src/task/step/steps/min_max_scale.py) (82 lines)
**Trust level: A- — 独立 oracle（未记录真实执行）**

## 1. 代码说明

Min-max scaling：接收 1 个输入，输出

> Min-max scaling to a configurable interval. NaNs are replaced with the axis minimum and constant axes become

关键符号：

- `class MinMaxScaleStep (line 13)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sample_dim, feature_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sample_dim` | `sample` | 样本维度 |
| `feature_dim` | `feature` | 特征维度 |
| `dim` | `sample` | 分析维度; choices: sample, feature |
| `output` | `` | 输出名称 |

## 2. 用途与解释

Min-max scaling to a configurable interval.

NaNs are replaced with the axis minimum and constant axes become zero.

## 3. 正确性依据

**结论：A- 级。** 独立实现「manual min-max scaling along the feature axis」，实测差值 2.915e-08。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | ORACLE | operator_table.csv:l2_oracle |
| L3 真实执行 | ROUTE | operator_table.csv:generated_route |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

独立 oracle 细节：

- 参考实现：manual min-max scaling along the feature axis
- 结果：pass=True, delta=2.9146690949666265e-08, tolerance=None

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
grep '^min_max_scale,' verification/coverage-8.0.1/operator_coverage.csv
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
