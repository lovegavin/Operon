# atac_tss_enrichment (`atac_tss_enrichment`)

**Category:** Quality Control  
**Entry point:** `src.task.step.steps.atac_tss_enrichment:AtacTssEnrichmentStep`  
**Source:** [`library/seed/src/task/step/steps/atac_tss_enrichment.py`](../../library/seed/src/task/step/steps/atac_tss_enrichment.py) (172 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Per-TSS fragment-density matrix and TSS enrichment score (ATAC-seq

> TSS enrichment matrix for ATAC-seq fragments. Inputs: A FileArtifact (format bam) B BED [tss, field] with chrom / chromStart / chromEnd / strand Output: 2D Form [tss, position] with fragment-midpoint counts per bin, plus the aggregate profile and the center/flank enrichment score in

关键符号：

- `class AtacTssEnrichmentStep (line 23)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=0, numeric=False, dims=(—), info=(representation)
- 输入 2: ndim=2, numeric=True, dims=(tss_region_dim, tss_field_dim), info=(encoders)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `flank` | `500` | Flank length (bp); min 100; max 5000 |
| `bin_size` | `10` | Bin size (bp); min 1; max 100 |
| `min_mapq` | `30` | Minimum mapping quality; min 0; max 255 |
| `exclude_duplicates` | `True` | Exclude duplicate reads |
| `max_records` | `0` | Maximum records; min 0 |
| `tss_region_dim` | `region` | TSS region dim |
| `tss_field_dim` | `field` | TSS field dim |
| `tss_chrom_field` | `chrom` | Chromosome column |
| `tss_start_field` | `chromStart` | Start column |
| `tss_end_field` | `chromEnd` | End column |
| `tss_strand_field` | `strand` | Strand column |
| `output` | `tss_enrichment` | Output name |

## 2. 用途与解释

TSS enrichment matrix for ATAC-seq fragments.

Inputs:
A  FileArtifact (format bam)
B  BED [tss, field] with chrom / chromStart / chromEnd / strand
Output:
2D Form [tss, position] with fragment-midpoint counts per bin, plus the
aggregate profile and the center/flank enrichment score in ``info``.

Count ATAC-seq fragment midpoints around transcription start sites.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension370.py |
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
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^atac_tss_enrichment,' verification/coverage-8.0.1/operator_coverage.csv
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
