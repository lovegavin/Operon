# Conditional logistic regression (`conditional_logistic`)

**Category:** Statistics  
**Entry point:** `src.task.step.steps.conditional_logistic:ConditionalLogisticStep`  
**Source:** [`library/seed/src/task/step/steps/conditional_logistic.py`](../../library/seed/src/task/step/steps/conditional_logistic.py) (335 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Fit a conditional logistic model for matched case-control

> Conditional logistic regression for matched case-control data. The conditional likelihood removes one intercept per stratum, so only within-stratum contrasts of the covariates are used. The implementation uses Newton-Raphson on the exact conditional likelihood and the observed information for standard errors. Output form ----------- dims = ["term", "statistic"] labels = {term: {covariate: i}, statistic: {"coef": 0, "se": 1, "z": 2, "P": 3, "CI_low": 4, "CI_high": 5, "OR": 6}} Params: stratum_label : column identifying matched sets (required) outcome_label : binary case/control column…

关键符号：

- `class ConditionalLogisticStep (line 142)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sample_dim, feature_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sample_dim` | `sample` | 样本维度 |
| `feature_dim` | `feature` | 特征维度 |
| `stratum_label` | `` | Stratum Label |
| `outcome_label` | `` | Outcome Label |
| `covariates` | `` | 协变量 |
| `confidence` | `0.95` | Confidence |
| `max_iter` | `100` | Max Iter; min 10 |
| `tol` | `1e-08` | Tol; max 0.001 |
| `output` | `` | 输出名称 |

## 2. 用途与解释

Conditional logistic regression for matched case-control data.

The conditional likelihood removes one intercept per stratum, so only
within-stratum contrasts of the covariates are used.  The implementation
uses Newton-Raphson on the exact conditional likelihood and the observed
information for standard errors.

Output form
-----------
dims    = ["term", "statistic"]
labels  = {term: {covariate: i},
statistic: {"coef": 0, "se": 1, "z": 2, "P": 3,
"CI_low": 4, "CI_high": 5, "OR": 6}}

Params:
stratum_label : column identifying matched sets (required)
outcome_label : binary case/control column (required)
covariates    : non-empty list of numeric covariate columns
confidence    : confidence level for coefficient intervals (default .95)
max_iter      : maximum Newton iterations (default 100)
tol           : convergence tolerance on the Newton step (default 1e-8)
output        : context key f

## 3. 正确性依据

**结论：B 级。** 真实运行通过（2.9 s），导出 1 行，产物 sha256 3a6ae4648c92ea13…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_conditional_logistic.py,test_r_oracles82.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/conditional_logistic |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 2.9 s，导出 1 行。
- 归档路线：`/tmp/cov_stats/conditional_logistic`。
- 命令：`cd /home/gavin/Operon && /home/gavin/bp-numpy21/bin/python scripts/run.py /tmp/cov_stats/conditional_logistic --check && /home/gavin/bp-numpy21/bin/python scripts/run.py /tmp/cov_stats/conditional_logistic`。

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
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^conditional_logistic,' verification/coverage-8.0.1/operator_coverage.csv
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
