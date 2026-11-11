# GTR tree likelihood (`phylogenetics_gtr_likelihood`)

**Category:** Phylogenetics  
**Entry point:** `src.task.step.steps.phylogenetics_gtr_likelihood:PhylogeneticsGtrLikelihoodStep`  
**Source:** [`library/seed/src/task/step/steps/phylogenetics_gtr_likelihood.py`](../../library/seed/src/task/step/steps/phylogenetics_gtr_likelihood.py) (160 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Felsenstein pruning log-likelihood of an alignment on a fixed Newick tree under a general time-reversible model with fixed exchangeabilities and base

> GTR likelihood of an alignment on a fixed Newick

关键符号：

- `def field_column() (line 12)`
- `def text_column() (line 19)`
- `def encoded_column() (line 34)`
- `def transition() (line 46)`
- `class PhylogeneticsGtrLikelihoodStep (line 59)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=False, dims=(tree_dim, field_dim), info=(—)
- 输入 2: ndim=2, numeric=False, dims=(taxon_dim, site_dim), info=(—)
- 输出: mode=declare, schema={"dims": ["entry", "statistic"], "numeric": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `base_freqs` | `0.25,0.25,0.25,0.25` | — |
| `rates` | `1.0,1.0,1.0,1.0,1.0,1.0` | — |
| `tree_dim` | `row` | — |
| `field_dim` | `field` | — |
| `taxon_dim` | `taxon` | — |
| `site_dim` | `site` | — |
| `output` | `gtr` | — |
| `tree_column` | `newick` | — |

## 2. 用途与解释

Felsenstein pruning log-likelihood for a fixed Newick tree and aligned nucleotide matrix under a general time-reversible model.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（3.04 s），导出 1 行，产物 sha256 58fd9d50da735d15…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_b80.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/phylogenetics_gtr_likelihood |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 3.04 s，导出 1 行。
- 归档路线：`/tmp/cov_stats/phylogenetics_gtr_likelihood`。
- 命令：`cd /home/gavin/Operon && /home/gavin/bp-numpy21/bin/python scripts/run.py /tmp/cov_stats/phylogenetics_gtr_likelihood --check && /home/gavin/bp-numpy21/bin/python scripts/run.py /tmp/cov_stats/phylogenetics_gtr_likelihood`。

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。

## 4. 限制与失败模式

Branch lengths and topology are fixed. The implementation assumes a reversible model and a single alignment.

## 5. 复现

```bash
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^phylogenetics_gtr_likelihood,' verification/coverage-8.0.1/operator_coverage.csv
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
