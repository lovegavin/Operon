# Site frequency spectrum (`site_frequency_spectrum`)

**Category:** Omics  
**Entry point:** `src.task.step.steps.site_frequency_spectrum:SiteFrequencySpectrumStep`  
**Source:** [`library/seed/src/task/step/steps/site_frequency_spectrum.py`](../../library/seed/src/task/step/steps/site_frequency_spectrum.py) (127 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Unfolded or folded site frequency spectrum of biallelic

> Site frequency spectrum for biallelic hard-call genotypes. For every variant the derived (alt) allele count is the number of alt alleles among the called chromosomes. The spectrum counts how many variants carry each count. Input: hard-call genotypes, [variant, sample], with the same number of called chromosomes on every variant (for example a complete genotype matrix, or a matrix subset that keeps only complete variants). Missing calls make the number of chromosomes vary between variants, which makes the folded spectrum ambiguous, so they are rejected instead of silently masked. Output: dims…

关键符号：

- `class SiteFrequencySpectrumStep (line 31)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(variant_dim, sample_dim), info=(missing_code, ploidy, representation)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `variant_dim` | `variant` | Variant Dim |
| `sample_dim` | `sample` | 样本维度 |
| `folded` | `False` | 折叠频谱 |
| `output` | `` | 输出名称 |

## 2. 用途与解释

Site frequency spectrum for biallelic hard-call genotypes.

For every variant the derived (alt) allele count is the number of alt
alleles among the called chromosomes. The spectrum counts how many
variants carry each count.

Input: hard-call genotypes, [variant, sample], with the same number of
called chromosomes on every variant (for example a complete genotype
matrix, or a matrix subset that keeps only complete variants). Missing
calls make the number of chromosomes vary between variants, which makes
the folded spectrum ambiguous, so they are rejected instead of silently
masked.

Output: dims [frequency, statistic] with columns (sites, proportion).
Unfolded bins are 1 .. n-1, folded bins are 1 .. n//2 with minor allele
counts (as in ``allel.sfs`` and ``allel.sfs_folded``). Monomorphic sites
(frequency 0 and n) are not part of the spectrum; ``proportion`` divides
the bin count by the to

## 3. 正确性依据

**结论：B 级。** 真实运行通过（3.19 s），导出 None 行，产物 sha256 08f8a376aa614e45…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_popgen_stats.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/site_frequency_spectrum |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 3.19 s，导出 None 行。
- 归档路线：`/tmp/cov_omics/site_frequency_spectrum`。
- 命令：`python scripts/run.py /tmp/cov_omics/site_frequency_spectrum`。

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
grep '^site_frequency_spectrum,' verification/coverage-8.0.1/operator_coverage.csv
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
