# vcf_relatedness (`vcf_relatedness`)

**Category:** Genome  
**Entry point:** `src.task.step.steps.vcf_relatedness:VcfRelatednessStep`  
**Source:** [`library/seed/src/task/step/steps/vcf_relatedness.py`](../../library/seed/src/task/step/steps/vcf_relatedness.py) (186 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

KING-robust between-family kinship coefficients between samples of a VCF (plink2 --make-king-table

> KING-robust kinship coefficients from a multi-sample VCF. The estimator is the KING-robust between-family formula (Manichaikul et al. 2010, Eq. 11), the same estimator used by plink2 `--make-king-table`: phi_ij = 1/2 - (N_IBS1 + 4 N_IBS0) / (4 min(N_Aa(i), N_Aa(j))) over autosomal biallelic SNPs where both samples are called, with N_IBS1 = N_Aa(i) + N_Aa(j) - 2 N_Aa,Aa. It is robust to population structure, so unrelated pairs centre near zero while duplicates and first-degree relatives move toward 0.5 and 0.25. Output: square 2D Form [sample, sample] (diagonal self-kinship

关键符号：

- `class VcfRelatednessStep (line 25)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=0, numeric=False, dims=(—), info=(representation)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `samples` | `` | — |
| `max_samples` | `50` | min 0 |
| `min_maf` | `0.05` | min 0.0; max 0.5 |
| `min_call_rate` | `0.9` | min 0.0; max 1.0 |
| `region` | `` | — |
| `max_variants` | `0` | min 0 |
| `output` | `vcf_relatedness` | — |

## 2. 用途与解释

KING-robust kinship coefficients from a multi-sample VCF.

The estimator is the KING-robust between-family formula (Manichaikul et al.
2010, Eq. 11), the same estimator used by plink2 `--make-king-table`:

phi_ij = 1/2 - (N_IBS1 + 4 N_IBS0) / (4 min(N_Aa(i), N_Aa(j)))

over autosomal biallelic SNPs where both samples are called, with
N_IBS1 = N_Aa(i) + N_Aa(j) - 2 N_Aa,Aa.  It is robust to population structure,
so unrelated pairs centre near zero while duplicates and first-degree relatives
move toward 0.5 and 0.25.

Output: square 2D Form [sample, sample] (diagonal self-kinship 0.5).

KING-robust kinship matrix for the selected VCF samples.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension363.py |
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
grep '^vcf_relatedness,' verification/coverage-8.0.1/operator_coverage.csv
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
