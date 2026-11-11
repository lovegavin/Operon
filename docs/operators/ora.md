# Gene-set ORA (`ora`)

**Category:** Omics  
**Entry point:** `src.task.step.steps.ora:OraStep`  
**Source:** [`library/seed/src/task/step/steps/ora.py`](../../library/seed/src/task/step/steps/ora.py) (177 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Gene-set ORA：接收 2 个输入，输出 Form；主要参数：Gene Dim、统计维度、Gene Set Dim、P 值字段、log2FC 字段、P

> Over-representation analysis (hypergeometric test) for gene sets. Inputs ------ stats : 2D [gene, statistic] with columns such as log2FC and Q_VALUE. sets : 2D [gene, gene_set] binary membership (for example GmtReader). The hit set is selected from ``stats`` by adjusted p-value and absolute log fold change. The universe is every gene present in ``stats``; genes in a set that are absent from the universe are ignored and counted in the export. This is the classical Fisher/hypergeometric ORA, not

关键符号：

- `class OraStep (line 39)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(gene_dim, stat_dim), info=(—)
- 输入 2: ndim=2, numeric=True, dims=(gene_dim, gene_set_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": false, "axis_info_open": false, "info": {"missing_code": {"type": ["number", "null"]}}}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `gene_dim` | `gene` | Gene Dim |
| `stat_dim` | `statistic` | 统计维度; advanced |
| `gene_set_dim` | `gene_set` | Gene Set Dim |
| `p_label` | `Q_VALUE` | P 值字段 |
| `lfc_label` | `log2FC` | log2FC 字段 |
| `p_threshold` | `0.05` | P 值阈值; min 0; max 1 |
| `lfc_threshold` | `0.0` | log2FC 阈值; min 0 |
| `direction` | `both` | Direction; choices: up, down, both |
| `correction` | `fdr` | Correction; choices: fdr, bonferroni, holm, hommel, fdr_by |
| `min_set_size` | `1` | Min Set Size; min 1 |
| `output` | `` | 输出名称 |

## 2. 用途与解释

Over-representation analysis (hypergeometric test) for gene sets.

Inputs
------
stats : 2D [gene, statistic] with columns such as log2FC and Q_VALUE.
sets  : 2D [gene, gene_set] binary membership (for example GmtReader).

The hit set is selected from ``stats`` by adjusted p-value and absolute
log fold change. The universe is every gene present in ``stats``; genes
in a set that are absent from the universe are ignored and counted in
the export.

This is the classical Fisher/hypergeometric ORA, not GSEA.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（2.78 s），导出 None 行，产物 sha256 9b4f2085d8624007…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension_operators.py,test_r_oracles.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/ora |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 2.78 s，导出 None 行。
- 归档路线：`/tmp/cov_omics/ora`。
- 命令：`python scripts/run.py /tmp/cov_omics/ora`。

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
grep '^ora,' verification/coverage-8.0.1/operator_coverage.csv
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
