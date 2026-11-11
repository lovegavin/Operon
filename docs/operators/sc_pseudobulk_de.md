# Pseudo-bulk differential expression (`sc_pseudobulk_de`)

**Category:** Single cell  
**Entry point:** `src.task.step.steps.sc_pseudobulk_de:ScPseudobulkDeStep`  
**Source:** [`library/seed/src/task/step/steps/sc_pseudobulk_de.py`](../../library/seed/src/task/step/steps/sc_pseudobulk_de.py) (77 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Aggregate cells by group and test gene-wise mean

> Pseudo-bulk differential

关键符号：

- `class ScPseudobulkDeStep (line 12)`
- `def export() (line 75)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=?, numeric=?, dims=(gene_dim, cell_dim), info=(—)
- 输入 2: ndim=?, numeric=?, dims=(cell_dim, field_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `gene_dim` | `gene` | Gene Dim |
| `cell_dim` | `cell` | Cell Dim |
| `field_dim` | `field` | Field Dim |
| `group_column` | `group` | Group Column |
| `output` | `de` | Output |

## 2. 用途与解释

Single-cell operator in the b64 panel. Inputs are numeric Form tables; output is a numeric Form.

Run `python -m operon registry build` after editing.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（3.03 s），导出 None 行，产物 sha256 4a3d828de7682a52…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_singlecell_panel_b64.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/sc_pseudobulk_de |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 3.03 s，导出 None 行。
- 归档路线：`/tmp/cov_omics/sc_pseudobulk_de`。
- 命令：`/home/gavin/bp-numpy21/bin/python scripts/run.py /tmp/cov_omics/sc_pseudobulk_de`。

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。

## 4. 限制与失败模式

相邻算子 Markdown 是参数约束与失败模式的权威说明；未找到单独的限制段。

## 5. 复现

```bash
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^sc_pseudobulk_de,' verification/coverage-8.0.1/operator_coverage.csv
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
