# Nucleotide Transformer variant effect (`nucleotide_transformer_variant_effect`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.nucleotide_transformer_variant_effect:NucleotideTransformerVariantEffectStep`  
**Source:** [`library/seed/src/task/step/steps/nucleotide_transformer_variant_effect.py`](../../library/seed/src/task/step/steps/nucleotide_transformer_variant_effect.py) (52 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Embeds reference and alternate windows and reports cosine distance and embedding

> Nucleotide Transformer variant effect from ref/alt

关键符号：

- `class NucleotideTransformerVariantEffectStep (line 12)`

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
| `ref_column` | `ref` | — |
| `alt_column` | `alt` | — |
| `model_path` | `` | — |
| `max_length` | `512` | min 16 |

## 2. 用途与解释

Compare reference and alternate sequence windows in Nucleotide Transformer embedding space.

## 3. 正确性依据

**结论：B 级。** 服务器真实运行通过（13.5849 s），1 个步骤产物，首个 sha256 b2376c74312014cd…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_b91.py |
| L3 真实执行 | EXECUTED_SRV | srv:/public/home/lihj/operon715/cov_nt/nucleotide_transformer_variant_effect/output/run_summary.json |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

服务器执行细节：

- 状态：complete，总耗时 13.5849 s，步骤 1。
- 路线：`/public/home/lihj/operon715/cov_nt/nucleotide_transformer_variant_effect`；run_id `20261110T194232-1a8f42fd8c79`。

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。

## 4. 限制与失败模式

Embedding-space distance is not a calibrated functional effect; identical windows are the
only exact control (cosine 1, distance 0). Windows are truncated at `max_length`.

## 5. 复现

```bash
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^nucleotide_transformer_variant_effect,' verification/coverage-8.0.1/operator_coverage.csv
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
