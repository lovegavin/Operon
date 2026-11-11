# One-sample t-test (`ttest_one_sample`)

**Category:** Statistics  
**Entry point:** `src.task.step.steps.ttest_one_sample:TTestOneSampleStep`  
**Source:** [`library/seed/src/task/step/steps/ttest_one_sample.py`](../../library/seed/src/task/step/steps/ttest_one_sample.py) (78 lines)
**Trust level: A- — 独立 oracle（未记录真实执行）**

## 1. 代码说明

One-sample t-test：接收 1 个输入，输出

> One-sample Student t-test against a fixed population

关键符号：

- `class TTestOneSampleStep (line 12)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sample_dim, feature_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sample_dim` | `sample` | 样本维度 |
| `feature_dim` | `feature` | 特征维度 |
| `popmean` | `0.0` | Popmean |
| `alternative` | `two-sided` | Alternative; choices: two-sided, less, greater |
| `output` | `` | 输出名称 |

## 2. 用途与解释

One-sample Student t-test against a fixed population mean.

## 3. 正确性依据

**结论：A- 级。** 独立实现「scipy.stats.ttest_1samp」，实测差值 4.243e-08。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | ORACLE | operator_table.csv:l2_oracle |
| L3 真实执行 | ROUTE | operator_table.csv:generated_route |
| L4 资源 | MEASURED | operator_table.csv:deterministic |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

独立 oracle 细节：

- 参考实现：scipy.stats.ttest_1samp
- 结果：pass=True, delta=4.243257545333279e-08, tolerance=None

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
grep '^ttest_one_sample,' verification/coverage-8.0.1/operator_coverage.csv
```

算子手册中的示例：

```text
Use the registry to discover compatible Readers and validate a complete workflow
before execution. This generated page does not claim an executable scientific
example. Add a tested example and replace this generated page with authored
guidance when extending this operator.
```

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
