# Flux balance analysis (`fba_flux_balance`)

**Category:** Metabolic modelling  
**Entry point:** `src.task.step.steps.fba_flux_balance:FbaFluxBalanceStep`  
**Source:** [`library/seed/src/task/step/steps/fba_flux_balance.py`](../../library/seed/src/task/step/steps/fba_flux_balance.py) (47 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Solve a steady-state flux balance linear program from a stoichiometric matrix and

> Auto-generated b83

关键符号：

- `class FbaFluxBalanceStep (line 11)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(row_dim, field_dim), info=(—)
- 输入 2: ndim=2, numeric=True, dims=(row_dim, field_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `row_dim` | `row` | — |
| `field_dim` | `field` | — |
| `output` | `output` | — |

## 2. 用途与解释

Solve a steady-state flux balance linear program from a stoichiometric matrix and bounds.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（2.73 s），导出 5 行，产物 sha256 b48257ef5ce8b0a2…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_b83.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/fba_flux_balance |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 2.73 s，导出 5 行。
- 归档路线：`/tmp/cov_stats/fba_flux_balance`。
- 命令：`cd /path/to/Operon-worktree && python scripts/run.py /tmp/cov_stats/fba_flux_balance --check && python scripts/run.py /tmp/cov_stats/fba_flux_balance`。

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。

## 4. 限制与失败模式

Deterministic closed-form implementation on the stated inputs; no model training or parameter estimation beyond least squares / linear programming.

## 5. 复现

```bash
cd /path/to/Operon-worktree
python -m operon registry check --json
grep '^fba_flux_balance,' verification/coverage-8.0.1/operator_coverage.csv
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
