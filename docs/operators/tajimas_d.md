# Tajima's D (`tajimas_d`)

**Category:** Omics  
**Entry point:** `src.task.step.steps.tajimas_d:TajimasDStep`  
**Source:** [`library/seed/src/task/step/steps/tajimas_d.py`](../../library/seed/src/task/step/steps/tajimas_d.py) (136 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Tajima's D over the whole input or fixed genomic

> Tajima's D over the whole input or fixed genomic windows. Tajima's D compares two estimates of the population mutation rate: pi sum over variants of the mean pairwise difference theta_w S / a1, with S the number of segregating sites and a1 = sum_{i=1}^{n-1} 1/i D = (pi - theta_w) / sqrt(e1 * S + e2 * S * (S - 1)) Input: hard-call genotypes, [variant, sample], alt allele counts in [0, ploidy], missing calls NaN. ``chrom`` and ``pos`` are read from the variant axis labels or from ``axis_info``. Windows follow scikit-allel: they start at the first annotated position, advance by ``step_size``…

关键符号：

- `class TajimasDStep (line 45)`

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
| `min_sites` | `3` | 最少分离位点数; min 1 |
| `output` | `` | 输出名称 |

## 2. 用途与解释

Tajima's D over the whole input or fixed genomic windows.

Tajima's D compares two estimates of the population mutation rate:

pi      sum over variants of the mean pairwise difference
theta_w S / a1, with S the number of segregating sites and
a1 = sum_{i=1}^{n-1} 1/i

D = (pi - theta_w) / sqrt(e1 * S + e2 * S * (S - 1))

Input: hard-call genotypes, [variant, sample], alt allele counts in
[0, ploidy], missing calls NaN. ``chrom`` and ``pos`` are read from the
variant axis labels or from ``axis_info``. Windows follow scikit-allel:
they start at the first annotated position, advance by ``step_size``
(default ``window_size``), are ``window_size`` long, and the last window
ends at the last position. The number of called chromosomes is the maximum
across the input, as in scikit-allel.

Output: dims [window, statistic] with columns
(start, end, n_variants, n_segregating, pi, theta_w, tajima_d)

## 3. 正确性依据

**结论：B 级。** 真实运行通过（3.01 s），导出 None 行，产物 sha256 4cc6a12200ea3923…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_popgen_stats.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/tajimas_d |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 3.01 s，导出 None 行。
- 归档路线：`/tmp/cov_omics/tajimas_d`。
- 命令：`python scripts/run.py /tmp/cov_omics/tajimas_d`。

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
grep '^tajimas_d,' verification/coverage-8.0.1/operator_coverage.csv
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
