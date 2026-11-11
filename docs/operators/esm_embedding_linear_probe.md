# ESM embedding linear probe (`esm_embedding_linear_probe`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.esm_embedding_linear_probe:EsmEmbeddingLinearProbeStep`  
**Source:** [`library/seed/src/task/step/steps/esm_embedding_linear_probe.py`](../../library/seed/src/task/step/steps/esm_embedding_linear_probe.py) (287 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Fit a standardised logistic-regression probe on an embedding table with stratified k-fold cross-validation and report per-fold accuracy, the mean and standard deviation, and the majority-class

> Cross-validated logistic-regression probe on protein embeddings. A linear probe is the standard sanity check for an embedding: if two labelled groups are separable with a linear model, the representation carries that signal. The operator standardises the features, runs stratified k-fold cross-validation and reports the per-fold accuracy together with the mean, the standard deviation and the majority-class

关键符号：

- `def parse_labels() (line 22)`
- `def resolve_labels() (line 29)`
- `def validate_input() (line 45)`
- `def probe_rows() (line 72)`
- `class EsmEmbeddingLinearProbeStep (line 138)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sample_dim, feature_dim), info=(encoders, missing_code)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sample_dim` | `sequence` | 样本维度 |
| `feature_dim` | `embedding` | 特征维度 |
| `labels` | `` | 标签 |
| `cv_folds` | `5` | 交叉验证折数; min 2; max 10 |
| `max_iter` | `1000` | 最大迭代次数; min 10 |
| `random_state` | `0` | 随机种子 |
| `output` | `probe` | 输出名称 |

## 2. 用途与解释

Cross-validated logistic-regression probe on protein embeddings.

A linear probe is the standard sanity check for an embedding: if two labelled
groups are separable with a linear model, the representation carries that
signal.  The operator standardises the features, runs stratified k-fold
cross-validation and reports the per-fold accuracy together with the mean, the
standard deviation and the majority-class baseline.

Stratified logistic-regression probe on a protein embedding form.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（0.8164 s），导出 8 行，产物 sha256 79d528b60fb2e10a…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension234.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/esm_embedding_linear_probe |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 0.8164 s，导出 8 行。
- 归档路线：`/tmp/probe_routes/esm_embedding_linear_probe`。
- 命令：`cd /home/gavin/Operon-7015-native && /home/gavin/bp-numpy21/bin/python scripts/run.py /tmp/probe_routes/esm_embedding_linear_probe`。

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
grep '^esm_embedding_linear_probe,' verification/coverage-8.0.1/operator_coverage.csv
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
