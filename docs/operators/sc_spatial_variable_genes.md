# Spatially variable genes (Moran's I) (`sc_spatial_variable_genes`)

**Category:** Single cell  
**Entry point:** `src.task.step.steps.sc_spatial_variable_genes:ScSpatialVariableGenesStep`  
**Source:** [`library/seed/src/task/step/steps/sc_spatial_variable_genes.py`](../../library/seed/src/task/step/steps/sc_spatial_variable_genes.py) (46 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Score each gene with Moran's I on a spatial kNN

关键符号：

- `class ScSpatialVariableGenesStep (line 10)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=?, numeric=?, dims=(row, field), info=(—)
- 输入 2: ndim=?, numeric=?, dims=(row, field), info=(—)
- 输出: mode=declare, schema={"type": "object", "additionalProperties": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `output` | `` | — |
| `row_dim` | `row` | — |
| `field_dim` | `field` | — |
| `k` | `6` | min 1; max 50 |

## 2. 用途与解释

Score each gene with Moran's I on a spatial kNN graph.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（2.29 s），导出 None 行，产物 sha256 0245fe00e5c27b4b…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_b65_panel.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/sc_spatial_variable_genes |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 2.29 s，导出 None 行。
- 归档路线：`/tmp/cov_omics/sc_spatial_variable_genes`。
- 命令：`/home/gavin/bp-numpy21/bin/python scripts/run.py /tmp/cov_omics/sc_spatial_variable_genes`。

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。

## 4. 限制与失败模式

Coordinates must share one scale; k-means is deterministic farthest-first and is not a full Leiden/SpaGCN model.

## 5. 复现

```bash
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^sc_spatial_variable_genes,' verification/coverage-8.0.1/operator_coverage.csv
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
