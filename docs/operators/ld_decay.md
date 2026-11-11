# LD decay (`ld_decay`)

**Category:** Omics  
**Entry point:** `src.task.step.steps.ld_decay:LdDecayStep`  
**Source:** [`library/seed/src/task/step/steps/ld_decay.py`](../../library/seed/src/task/step/steps/ld_decay.py) (171 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

LD decay: binned mean r^2 between variant dosages by

> Linkage disequilibrium decay over genomic distance. For every pair of variants on one chromosome the squared Pearson correlation of the alt allele dosage (0 .. ploidy) is computed, which equals ``allel.rogers_huff_r`` squared for complete hard calls. Pairs are binned by physical distance in ``n_bins`` equal-width bins between 0 and ``max_distance`` base pairs; zero-distance pairs (duplicate positions) are excluded because they are not independent loci. Input: hard-call genotypes, [variant, sample], with ``pos`` and ``chrom`` read from the variant axis labels or from ``axis_info``. Only…

关键符号：

- `class LdDecayStep (line 36)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(variant_dim, sample_dim), info=(chrom, missing_code, ploidy, pos, representation)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `variant_dim` | `variant` | Variant Dim |
| `sample_dim` | `sample` | 样本维度 |
| `max_distance` | `100000` | 最大距离; min 1 |
| `n_bins` | `20` | 分箱数; min 2; max 500 |
| `max_pairs` | `5000000` | 最大配对数; min 2 |
| `output` | `` | 输出名称 |

## 2. 用途与解释

Linkage disequilibrium decay over genomic distance.

For every pair of variants on one chromosome the squared Pearson
correlation of the alt allele dosage (0 .. ploidy) is computed, which equals
``allel.rogers_huff_r`` squared for complete hard calls. Pairs are binned by
physical distance in ``n_bins`` equal-width bins between 0 and
``max_distance`` base pairs; zero-distance pairs (duplicate positions) are
excluded because they are not independent loci.

Input: hard-call genotypes, [variant, sample], with ``pos`` and ``chrom``
read from the variant axis labels or from ``axis_info``. Only complete
variants (no missing call) and polymorphic variants (non-zero variance)
enter the correlation. The input must span a single chromosome; subset a
chromosome first when a VCF covers more.

Output: dims [distance_bin, statistic] with columns
(bin_start, bin_end, n_pairs, mean_r2, median_r2). Empty 

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_popgen_stats.py |
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
grep '^ld_decay,' verification/coverage-8.0.1/operator_coverage.csv
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
