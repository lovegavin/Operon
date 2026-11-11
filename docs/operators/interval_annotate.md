# Annotate intervals by feature class (`interval_annotate`)

**Category:** Genome  
**Entry point:** `src.task.step.steps.interval_annotate:IntervalAnnotateStep`  
**Source:** [`library/seed/src/task/step/steps/interval_annotate.py`](../../library/seed/src/task/step/steps/interval_annotate.py) (224 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Assign every BED interval to the highest-priority genomic feature class it overlaps (for example promoter before exon before intron), and report the number of classes and overlapped

> Annotate BED intervals with genomic feature

关键符号：

- `def annotate_intervals() (line 15)`
- `class IntervalAnnotateStep (line 65)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(interval_region_dim, interval_field_dim), info=(—)
- 输入 2: ndim=2, numeric=True, dims=(feature_region_dim, feature_field_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `interval_region_dim` | `region` | Region axis |
| `interval_field_dim` | `field` | Field axis |
| `interval_chrom_field` | `chrom` | Chromosome column |
| `interval_start_field` | `chromStart` | Start column |
| `interval_end_field` | `chromEnd` | End column |
| `feature_region_dim` | `region` | Region axis |
| `feature_field_dim` | `field` | Field axis |
| `feature_chrom_field` | `chrom` | Chromosome column |
| `feature_start_field` | `chromStart` | Start column |
| `feature_end_field` | `chromEnd` | End column |
| `class_field` | `name` | Feature class column |
| `class_names` | `promoter,utr5,cds,utr3,exon,intron` | Class names |
| `priority` | `promoter,utr5,cds,utr3,exon,intron` | Class priority |
| `output` | `annotation` | Output name |

## 2. 用途与解释

Annotate BED intervals with genomic feature classes.

Assign each interval to the highest-priority overlapping feature class.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension374.py |
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
grep '^interval_annotate,' verification/coverage-8.0.1/operator_coverage.csv
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
