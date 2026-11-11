# Exact two-sample Poisson rate test (`poisson_means_test`)

**Category:** Statistics  
**Entry point:** `src.task.step.steps.poisson_means_test:PoissonMeansTestStep`  
**Source:** [`library/seed/src/task/step/steps/poisson_means_test.py`](../../library/seed/src/task/step/steps/poisson_means_test.py) (138 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Exact two-sample Poisson rate test：接收 2 个输入，输出 Form；主要参数：特征维度、样本维度、分组维度、分组字段、A 组、B

> Exact two-sample Poisson rate test via conditional

关键符号：

- `class PoissonMeansTestStep (line 20)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(feature_dim, sample_dim), info=(—)
- 输入 2: ndim=2, numeric=True, dims=(sample_dim, group_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `feature_dim` | `feature` | 特征维度 |
| `sample_dim` | `sample` | 样本维度 |
| `group_dim` | `sample` | 分组维度 |
| `group_label` | `` | 分组字段 |
| `group_a` | `` | A 组 |
| `group_b` | `` | B 组 |
| `alternative` | `two-sided` | Alternative; choices: two-sided, less, greater |
| `confidence` | `0.95` | Confidence |
| `output` | `` | 输出名称 |

## 2. 用途与解释

Exact two-sample Poisson rate test via conditional binomial.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（2.91 s），导出 5 行，产物 sha256 ffba76e661250922…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension64.py,test_r_oracles55.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/poisson_means_test |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 2.91 s，导出 5 行。
- 归档路线：`/tmp/cov_stats/poisson_means_test`。
- 命令：`cd /home/gavin/Operon && /home/gavin/bp-numpy21/bin/python scripts/run.py /tmp/cov_stats/poisson_means_test --check && /home/gavin/bp-numpy21/bin/python scripts/run.py /tmp/cov_stats/poisson_means_test`。

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
grep '^poisson_means_test,' verification/coverage-8.0.1/operator_coverage.csv
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
