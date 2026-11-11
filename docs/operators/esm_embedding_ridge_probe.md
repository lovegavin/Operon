# Embedding ridge regression probe (`esm_embedding_ridge_probe`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.esm_embedding_ridge_probe:EsmEmbeddingRidgeProbeStep`  
**Source:** [`library/seed/src/task/step/steps/esm_embedding_ridge_probe.py`](../../library/seed/src/task/step/steps/esm_embedding_ridge_probe.py) (306 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Fit a cross-validated ridge regression from per-sequence embedding vectors to a continuous property (for example a fitness or stability measurement) and report per-fold R2, RMSE and MAE with a mean

> Cross-validated ridge regression on embedding

关键符号：

- `def parse_targets() (line 14)`
- `def resolve_targets() (line 29)`
- `def validate_input() (line 52)`
- `def ridge_predict() (line 87)`
- `def probe_rows() (line 112)`
- `class EsmEmbeddingRidgeProbeStep (line 181)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sample_dim, feature_dim), info=(labels, representation)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sample_dim` | `sequence` | 样本维度名 |
| `feature_dim` | `embedding` | 特征维度名 |
| `metric_dim` | `metric` | 指标维度名 |
| `targets` | `` | 目标值 |
| `cv_folds` | `5` | 折数; min 2; max 10 |
| `alpha` | `1.0` | 正则强度; min 1e-06; max 1000000 |
| `standardize` | `True` | 标准化 |
| `random_state` | `0` | 随机种子 |
| `output` | `probe` | 输出 |

## 2. 用途与解释

Cross-validated ridge regression on embedding vectors.

Predict a continuous property from ESM embeddings with ridge regression.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（0.0038 s），导出 9 行，产物 sha256 5551e8a4c0c9465d…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension270.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/esm_embedding_ridge_probe |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 0.0038 s，导出 9 行。
- 归档路线：`/tmp/probe_routes/esm_embedding_ridge_probe`。
- 命令：`cd /path/to/Operon-worktree && python scripts/run.py /tmp/probe_routes/esm_embedding_ridge_probe`。

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
grep '^esm_embedding_ridge_probe,' verification/coverage-8.0.1/operator_coverage.csv
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
