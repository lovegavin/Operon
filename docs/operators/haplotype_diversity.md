# Haplotype and nucleotide diversity (`haplotype_diversity`)

**Category:** Population genetics  
**Entry point:** `src.task.step.steps.haplotype_diversity:HaplotypeDiversityStep`  
**Source:** [`library/seed/src/task/step/steps/haplotype_diversity.py`](../../library/seed/src/task/step/steps/haplotype_diversity.py) (59 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Haplotype and nucleotide

> Haplotype and nucleotide

关键符号：

- `class HaplotypeDiversityStep (line 16)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(row_dim, field_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `row_dim` | `row` | — |
| `field_dim` | `field` | — |
| `output` | `diversity` | — |

## 2. 用途与解释

Counts distinct haplotypes and reports Nei's haplotype diversity, average pairwise nucleotide diversity and the number of segregating sites.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（2.3 s），导出 1 行，产物 sha256 d33ccfc2d9f11dbd…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_b81.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/haplotype_diversity |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 2.3 s，导出 1 行。
- 归档路线：`/tmp/cov_stats/haplotype_diversity`。
- 命令：`cd /path/to/Operon-worktree && python scripts/run.py /tmp/cov_stats/haplotype_diversity --check && python scripts/run.py /tmp/cov_stats/haplotype_diversity`。

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。

## 4. 限制与失败模式

The implementation works on small alignments, treats stop codons as
non-synonymous and does not model gap characters.

## 5. 复现

```bash
cd /path/to/Operon-worktree
python -m operon registry check --json
grep '^haplotype_diversity,' verification/coverage-8.0.1/operator_coverage.csv
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
