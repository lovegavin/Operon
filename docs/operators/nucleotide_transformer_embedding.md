# Nucleotide Transformer embeddings (`nucleotide_transformer_embedding`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.nucleotide_transformer_embedding:NucleotideTransformerEmbeddingStep`  
**Source:** [`library/seed/src/task/step/steps/nucleotide_transformer_embedding.py`](../../library/seed/src/task/step/steps/nucleotide_transformer_embedding.py) (46 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Mean-pooled 512-d embeddings from the Nucleotide Transformer v2 50M multi-species

> Mean-pooled Nucleotide Transformer

关键符号：

- `class NucleotideTransformerEmbeddingStep (line 13)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(row_dim, field_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `row_dim` | `row` | — |
| `field_dim` | `field` | — |
| `output` | `` | — |
| `sequence_column` | `seq` | — |
| `model_path` | `` | — |
| `max_length` | `512` | min 16 |
| `batch_size` | `8` | min 1 |

## 2. 用途与解释

Compute mean-pooled embeddings with the Nucleotide Transformer v2 50M multi-species model.

## 3. 正确性依据

**结论：B 级。** 服务器真实运行通过（18.0289 s），1 个步骤产物，首个 sha256 b271804cec3e5d89…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_b91.py |
| L3 真实执行 | EXECUTED_SRV | srv:/public/home/lihj/operon715/cov_nt/nucleotide_transformer_embedding/output/run_summary.json |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

服务器执行细节：

- 状态：complete，总耗时 18.0289 s，步骤 1。
- 路线：`/public/home/lihj/operon715/cov_nt/nucleotide_transformer_embedding`；run_id `20261110T194211-e313da5486bb`。

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。

## 4. 限制与失败模式

CPU inference only. Sequences longer than `max_length` are truncated (k-mer tokens).
Mean pooling includes special tokens.

## 5. 复现

```bash
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^nucleotide_transformer_embedding,' verification/coverage-8.0.1/operator_coverage.csv
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
