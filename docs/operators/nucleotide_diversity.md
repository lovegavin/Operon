# Nucleotide diversity (`nucleotide_diversity`)

**Category:** Omics  
**Entry point:** `src.task.step.steps.nucleotide_diversity:NucleotideDiversityStep`  
**Source:** [`library/seed/src/task/step/steps/nucleotide_diversity.py`](../../library/seed/src/task/step/steps/nucleotide_diversity.py) (119 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Nucleotide diversity over the whole input or fixed genomic

> Nucleotide diversity (pi) over the whole input or fixed genomic windows. Nucleotide diversity is the average number of differences between two chromosomes sampled from the input: pi sum over variants of the mean pairwise difference pi_per_site pi / n_bases Input: hard-call genotypes, [variant, sample], alt allele counts in [0, ploidy], missing calls NaN. ``chrom`` and ``pos`` are read from the variant axis labels or from ``axis_info``. Windows follow scikit-allel: they start at the first annotated position, advance by ``step_size`` (default ``window_size``), are ``window_size`` long, and the…

关键符号：

- `class NucleotideDiversityStep (line 42)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(variant_dim, sample_dim), info=(missing_code, ploidy, representation)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `variant_dim` | `variant` | Variant Dim |
| `sample_dim` | `sample` | 样本维度 |
| `window_size` | `None` | 窗口大小 |
| `step_size` | `None` | 步长 |
| `output` | `` | 输出名称 |

## 2. 用途与解释

Nucleotide diversity (pi) over the whole input or fixed genomic windows.

Nucleotide diversity is the average number of differences between two
chromosomes sampled from the input:

pi            sum over variants of the mean pairwise difference
pi_per_site   pi / n_bases

Input: hard-call genotypes, [variant, sample], alt allele counts in
[0, ploidy], missing calls NaN. ``chrom`` and ``pos`` are read from the
variant axis labels or from ``axis_info``. Windows follow scikit-allel:
they start at the first annotated position, advance by ``step_size``
(default ``window_size``), are ``window_size`` long, and the last window
ends at the last position.

Output: dims [window, statistic] with columns
(start, end, n_variants, n_bases, pi, pi_per_site, mean_pairwise_difference).
Without ``pos`` there is one row per chromosome, start/end and n_bases are
NaN, and only the absolute ``pi`` is meaningfu

## 3. 正确性依据

**结论：B 级。** 真实运行通过（2.96 s），导出 None 行，产物 sha256 f068d10139c3cbed…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_popgen_stats.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/nucleotide_diversity |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 2.96 s，导出 None 行。
- 归档路线：`/tmp/cov_omics/nucleotide_diversity`。
- 命令：`/home/gavin/bp-numpy21/bin/python scripts/run.py /tmp/cov_omics/nucleotide_diversity`。

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
grep '^nucleotide_diversity,' verification/coverage-8.0.1/operator_coverage.csv
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
