# Cohen's kappa (`cohens_kappa`)

**Category:** Statistics  
**Entry point:** `src.task.step.steps.cohens_kappa:CohensKappaStep`  
**Source:** [`library/seed/src/task/step/steps/cohens_kappa.py`](../../library/seed/src/task/step/steps/cohens_kappa.py) (82 lines)
**Trust level: A — 独立 oracle + 真实执行**

## 1. 代码说明

Cohen's kappa：接收 1 个输入，输出 Form；主要参数：Row Dim、Col

> Cohen's kappa for two raters on a contingency

关键符号：

- `class CohensKappaStep (line 16)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(row_dim, col_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `row_dim` | `rater_a` | Row Dim |
| `col_dim` | `rater_b` | Col Dim |
| `weights` | `none` | Weights; choices: none, linear, quadratic |
| `output` | `` | 输出名称 |

## 2. 用途与解释

Cohen's kappa for two raters on a contingency table.

## 3. 正确性依据

**结论：A 级。** 独立实现「hand-computed Cohen kappa from the contingency table」，实测差值 1.877e-08。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | ORACLE | operator_table.csv:l2_oracle |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/cohens_kappa |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

独立 oracle 细节：

- 参考实现：hand-computed Cohen kappa from the contingency table
- 结果：pass=True, delta=1.8769122145378958e-08, tolerance=1e-07
- 说明：operator rounds kappa to 8 decimals

本次执行细节：

- 状态：PASS，耗时 2.9 s，导出 6 行。
- 归档路线：`/tmp/cov_stats/cohens_kappa`。
- 命令：`cd /path/to/Operon-worktree && python scripts/run.py /tmp/cov_stats/cohens_kappa --check && python scripts/run.py /tmp/cov_stats/cohens_kappa`。

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
grep '^cohens_kappa,' verification/coverage-8.0.1/operator_coverage.csv
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
