# Preranked GSEA (`gsea`)

**Category:** Omics  
**Entry point:** `src.task.step.steps.gsea:GseaStep`  
**Source:** [`library/seed/src/task/step/steps/gsea.py`](../../library/seed/src/task/step/steps/gsea.py) (200 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Preranked GSEA：接收 2 个输入，输出 Form；主要参数：Gene Dim、统计维度、Gene Set Dim、Rank

> Preranked Gene Set Enrichment Analysis (GSEA). This is the classical weighted Kolmogorov-Smirnov enrichment score (Subramanian et al. 2005), followed by gene-set permutation p-values and BH correction. It is intentionally labelled *preranked*: it does not reorder samples or estimate per-sample phenotypes. Inputs ------ ranked : [gene, statistic] with a ranking column (default log2FC) sets : [gene, gene_set] binary membership The gene-set permutation null is the standard choice for preranked GSEA when sample-level expression is not available. The number of permutations is explicit and seeded;…

关键符号：

- `class GseaStep (line 61)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(gene_dim, stat_dim), info=(—)
- 输入 2: ndim=2, numeric=True, dims=(gene_dim, gene_set_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": false, "axis_info_open": false, "info": {"missing_code": {"type": ["number", "null"]}}}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `gene_dim` | `gene` | Gene Dim |
| `stat_dim` | `statistic` | 统计维度; advanced |
| `gene_set_dim` | `gene_set` | Gene Set Dim |
| `rank_label` | `log2FC` | Rank Label |
| `weight` | `1.0` | Weight; min 0 |
| `n_permutations` | `1000` | 置换次数; min 10 |
| `seed` | `0` | Seed |
| `min_set_size` | `5` | Min Set Size; min 1 |
| `max_set_size` | `500` | Max Set Size; min 1 |
| `correction` | `fdr` | Correction; choices: fdr, bonferroni, holm, hommel, fdr_by |
| `output` | `` | 输出名称 |

## 2. 用途与解释

Preranked Gene Set Enrichment Analysis (GSEA).

This is the classical weighted Kolmogorov-Smirnov enrichment score
(Subramanian et al. 2005), followed by gene-set permutation p-values
and BH correction. It is intentionally labelled *preranked*: it does
not reorder samples or estimate per-sample phenotypes.

Inputs
------
ranked : [gene, statistic] with a ranking column (default log2FC)
sets   : [gene, gene_set] binary membership

The gene-set permutation null is the standard choice for preranked
GSEA when sample-level expression is not available. The number of
permutations is explicit and seeded; results are reproducible.

This implementation is independent of fgsea/clusterProfiler. The test
suite compares the enrichment-score calculation and null behavior.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension_operators.py,test_r_oracles.py |
| L3 真实执行 | ROUTE | operator_table.csv:builtin_route |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。
- 注意：该算子没有独立数值 oracle， correctness 仅到“契约/测试/执行”层级。

## 4. 限制与失败模式

Declared memory modes: full. Operon retains the existing planner, disk-backed
inputs and emergency spill behavior; full-mode operators still require their
declared working set. This generated reference has not been independently
scientifically reviewed.

## 5. 复现

```bash
cd /path/to/Operon-worktree
python -m operon registry check --json
grep '^gsea,' verification/coverage-8.0.1/operator_coverage.csv
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
