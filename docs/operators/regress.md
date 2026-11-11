# 回归分析 (`regress`)

**Category:** 统计分析  
**Entry point:** `src.task.step.steps.regress:RegressStep`  
**Source:** [`library/seed/src/task/step/steps/regress.py`](../../library/seed/src/task/step/steps/regress.py) (343 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

逐个特征拟合回归模型，可加入协变量。

> Multiple regression over one dimension of a wide form. Input is a single wide form. One position along a chosen dimension is the response; a set of other positions are covariates; all remaining positions are tested one at a time as predictors. For each predictor, the operator fits: response ~ predictor + covariates Failure policy -------------- A predictor is skipped, with a recorded reason, only when a known condition prevents a meaningful fit: * too few valid samples * predictor is constant * binary response has a single class in this subset * design matrix is rank-deficient * logistic fit…

关键符号：

- `class RegressStep (line 39)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(dim), info=(—)
- 输出: mode=regress, schema={}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `dim` | `` | 特征维度 |
| `response` | `` | 响应变量标签 |
| `covariates` | `[]` | 协变量标签 |
| `method` | `auto` | 模型; choices: auto, ols, logit |

## 2. 用途与解释

Multiple regression over one dimension of a wide form.

Input is a single wide form. One position along a chosen dimension is
the response; a set of other positions are covariates; all remaining
positions are tested one at a time as predictors.

For each predictor, the operator fits:

response ~ predictor + covariates

Failure policy
--------------
A predictor is skipped, with a recorded reason, only when a known
condition prevents a meaningful fit:

* too few valid samples
* predictor is constant
* binary response has a single class in this subset
* design matrix is rank-deficient
* logistic fit hits perfect separation
* the fit returned non-finite estimates

Any other exception propagates. Nothing is silently swallowed.

Regression of a response on each predictor, adjusting for covariates.

Params:
dim        : dimension to iterate over
response   : label of the response column
covaria

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_contracts.py |
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
grep '^regress,' verification/coverage-8.0.1/operator_coverage.csv
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
