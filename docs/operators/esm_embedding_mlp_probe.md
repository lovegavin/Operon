# ESM embedding MLP probe (`esm_embedding_mlp_probe`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.esm_embedding_mlp_probe:EsmEmbeddingMlpProbeStep`  
**Source:** [`library/seed/src/task/step/steps/esm_embedding_mlp_probe.py`](../../library/seed/src/task/step/steps/esm_embedding_mlp_probe.py) (291 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Fit a standardised multi-layer perceptron on an embedding table with stratified k-fold cross-validation and report per-fold accuracy, the mean and standard deviation, and the majority-class baseline against the linear

> Non-linear probe over an ESM embedding table with a scikit-learn MLP. The linear probe (``esm_embedding_linear_probe``) answers "is the signal linearly decodable?". This operator fits a small multi-layer perceptron with stratified k-fold cross-validation, which shows whether a curved decision boundary buys anything over the linear

关键符号：

- `def parse_labels() (line 21)`
- `def resolve_labels() (line 33)`
- `def validate_input() (line 48)`
- `def mlp_rows() (line 77)`
- `class EsmEmbeddingMlpProbeStep (line 146)`

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
| `hidden` | `32` | 隐藏层宽度; min 2; max 512 |
| `alpha` | `0.001` | L2 正则 |
| `max_iter` | `600` | 迭代上限; min 10; max 20000 |
| `random_state` | `0` | 随机种子 |
| `output` | `probe` | 输出槽 |

## 2. 用途与解释

Non-linear probe over an ESM embedding table with a scikit-learn MLP.

The linear probe (``esm_embedding_linear_probe``) answers "is the signal
linearly decodable?".  This operator fits a small multi-layer perceptron with
stratified k-fold cross-validation, which shows whether a curved decision
boundary buys anything over the linear baseline.

Stratified MLP probe on a protein embedding form.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（0.7058 s），导出 8 行，产物 sha256 f1e784f8ee968fa5…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension271.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/esm_embedding_mlp_probe |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 0.7058 s，导出 8 行。
- 归档路线：`/tmp/probe_routes/esm_embedding_mlp_probe`。
- 命令：`cd /path/to/Operon-worktree && python scripts/run.py /tmp/probe_routes/esm_embedding_mlp_probe`。

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
grep '^esm_embedding_mlp_probe,' verification/coverage-8.0.1/operator_coverage.csv
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
