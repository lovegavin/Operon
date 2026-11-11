# atac_peak_call (`atac_peak_call`)

**Category:** Quality Control  
**Entry point:** `src.task.step.steps.atac_peak_call:AtacPeakCallStep`  
**Source:** [`library/seed/src/task/step/steps/atac_peak_call.py`](../../library/seed/src/task/step/steps/atac_peak_call.py) (144 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Call ATAC/ChIP peaks from a BAM file with a local Poisson model and BH

> Poisson peak calling for ATAC-seq / ChIP-seq BAM

关键符号：

- `class AtacPeakCallStep (line 16)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=0, numeric=False, dims=(—), info=(representation)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "labels": {"field": ["start", "end", "length", "summit", "count", "score", "fold_enrichment"]}}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `min_mapq` | `30` | Minimum mapping quality for; min 0; max 60 |
| `qvalue` | `0.05` | Benjamini-Hochberg q-value; max 1 |
| `max_gap` | `50` | Maximum gap between significant bases merged into one; min 1; max 100000 |
| `min_length` | `100` | Minimum peak length in base; min 1; max 100000 |
| `window_1kb` | `1000` | Short local window for the Poisson; min 101; max 100001 |
| `window_10kb` | `10000` | Long local window for the Poisson; min 1001; max 1000001 |
| `max_fragments` | `0` | Optional cap on the number of fragments (0 =; min 0 |
| `output` | `peaks` | Name of the output peak |
| `candidate_sigma` | `3.0` | Candidate enrichment threshold in local standard |
| `extension_bp` | `260` | Bases added on each side of a significant; min 0 |

## 2. 用途与解释

Poisson peak calling for ATAC-seq / ChIP-seq BAM files.

Call peaks from fragment pileup with a local Poisson model.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_l2_gap.py |
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
grep '^atac_peak_call,' verification/coverage-8.0.1/operator_coverage.csv
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
