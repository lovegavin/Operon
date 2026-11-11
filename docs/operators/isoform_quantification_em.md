# Isoform quantification (EM) (`isoform_quantification_em`)

**Category:** Transcriptomics  
**Entry point:** `src.task.step.steps.isoform_quantification_em:IsoformQuantificationEmStep`  
**Source:** [`library/seed/src/task/step/steps/isoform_quantification_em.py`](../../library/seed/src/task/step/steps/isoform_quantification_em.py) (79 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

EM over an isoform/exon compatibility matrix and exon read

> EM over an isoform/exon compatibility matrix and exon read

关键符号：

- `class IsoformQuantificationEmStep (line 8)`
- `def export() (line 77)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(isoform_dim, exon_dim), info=(—)
- 输入 2: ndim=2, numeric=True, dims=(exon_dim, sample_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `row_dim` | `isoform` | Row dimension |
| `output` | `output` | Output parameter |
| `isoform_dim` | `isoform` | Isoform dimension |
| `exon_dim` | `exon` | Exon dimension |
| `sample_dim` | `sample` | Sample dimension |
| `max_iter` | `200` | Maximum EM iterations; min 1; max 100000 |
| `tol` | `1e-08` | EM convergence tolerance; min 0.0 |

## 2. 用途与解释

EM over an isoform/exon compatibility matrix and exon read counts.

Synthetic tables and public annotation layouts only; no biological conclusion.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（1.69 s），导出 None 行，产物 sha256 6d999771bb2c8129…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_splicing_panel_b73.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/isoform_quantification_em |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 1.69 s，导出 None 行。
- 归档路线：`/tmp/cov_omics/isoform_quantification_em`。
- 命令：`python scripts/run.py /tmp/cov_omics/isoform_quantification_em`。

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。

## 4. 限制与失败模式

相邻算子 Markdown 是参数约束与失败模式的权威说明；未找到单独的限制段。

## 5. 复现

```bash
cd /path/to/Operon-worktree
python -m operon registry check --json
grep '^isoform_quantification_em,' verification/coverage-8.0.1/operator_coverage.csv
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
