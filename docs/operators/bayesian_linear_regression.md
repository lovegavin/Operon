# Bayesian linear regression (`bayesian_linear_regression`)

**Category:** Statistics  
**Entry point:** `src.task.step.steps.bayesian_linear_regression:BayesianLinearRegressionStep`  
**Source:** [`library/seed/src/task/step/steps/bayesian_linear_regression.py`](../../library/seed/src/task/step/steps/bayesian_linear_regression.py) (50 lines)
**Trust level: A- — 独立 oracle（未记录真实执行）**

## 1. 代码说明

Gibbs sampling for a normal-inverse-gamma linear model with weakly informative

> Bayesian linear regression

关键符号：

- `class BayesianLinearRegressionStep (line 12)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(row_dim, field_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `output` | `bayesian_linear_regression_out` | — |
| `row_dim` | `row` | — |
| `field_dim` | `field` | — |
| `y_column` | `y` | — |
| `covariate_columns` | `x1` | — |
| `n_samples` | `2000` | — |
| `burn_in` | `500` | — |
| `prior_scale` | `10.0` | — |
| `shape` | `0.01` | — |
| `scale` | `0.01` | — |
| `seed` | `7` | — |

## 2. 用途与解释

Implements `bayesian_linear_regression` as a self-contained Bayesian estimator. The
operator reads one table Form, treats the configured outcome and covariate columns
as numeric fields, runs a Gibbs sampler over the regression coefficients and the
residual variance, and returns one row per parameter with posterior mean, standard
deviation, credible interval and the posterior mean of sigma squared.

## 3. 正确性依据

**结论：A- 级。** 独立实现「statsmodels/numpy OLS」，实测差值 4.800e-04。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | ORACLE | operator_table.csv:l2_oracle |
| L3 真实执行 | ROUTE | operator_table.csv:generated_route |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

独立 oracle 细节：

- 参考实现：statsmodels/numpy OLS
- 结果：pass=True, delta=0.0004800184681807984, tolerance=None

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。

## 4. 限制与失败模式

The sampler assumes independent Gaussian errors and a linear mean. It is intended
for screening and teaching, not for model selection or hierarchical structure.

## 5. 复现

```bash
cd /path/to/Operon-worktree
python -m operon registry check --json
grep '^bayesian_linear_regression,' verification/coverage-8.0.1/operator_coverage.csv
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
