# Split conformal prediction intervals for regression (`conformal_split_regression`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.conformal_split_regression:ConformalSplitRegressionStep`  
**Source:** [`library/seed/src/task/step/steps/conformal_split_regression.py`](../../library/seed/src/task/step/steps/conformal_split_regression.py) (57 lines)
**Trust level: A- — 独立 oracle（未记录真实执行）**

## 1. 代码说明

Distribution-free split-conformal regression intervals with finite-sample

> Split conformal prediction intervals for

关键符号：

- `class ConformalSplitRegressionStep (line 16)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(row_dim, field_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `row_dim` | `row` | — |
| `field_dim` | `field` | — |
| `output` | `output` | — |
| `alpha` | `0.1` | min 0.001; max 0.999 |

## 2. 用途与解释

Distribution-free split-conformal regression intervals with finite-sample coverage.

## 3. 正确性依据

**结论：A- 级。** 独立实现「empirical split-conformal quantile」，算子 0.803264099 vs 参考 0.8032640994328629。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | ORACLE | operator_table.csv:l2_oracle |
| L3 真实执行 | ROUTE | operator_table.csv:generated_route |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

独立 oracle 细节：

- 参考实现：empirical split-conformal quantile
- 结果：pass=True, delta=None, tolerance=None

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。

## 4. 限制与失败模式

Synthetic or small tabular inputs are intended for deterministic verification; this is not a replacement for a full probabilistic-programming workflow.

## 5. 复现

```bash
cd /path/to/Operon-worktree
python -m operon registry check --json
grep '^conformal_split_regression,' verification/coverage-8.0.1/operator_coverage.csv
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
