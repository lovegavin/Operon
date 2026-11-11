# Leiden clustering (`sc_leiden_cluster`)

**Category:** Single cell  
**Entry point:** `src.task.step.steps.sc_leiden_cluster:ScLeidenClusterStep`  
**Source:** [`library/seed/src/task/step/steps/sc_leiden_cluster.py`](../../library/seed/src/task/step/steps/sc_leiden_cluster.py) (64 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Leiden community detection over a cell-cell

> Leiden community detection on a cell

关键符号：

- `class ScLeidenClusterStep (line 14)`
- `def export() (line 62)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=?, numeric=?, dims=(cell_dim, cell2_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `cell_dim` | `cell` | Cell Dim |
| `cell2_dim` | `cell2` | Cell2 Dim |
| `resolution` | `1.0` | Resolution; min 0.01; max 20.0 |
| `seed` | `0` | Seed |
| `output` | `clusters` | Output |

## 2. 用途与解释

Single-cell operator in the b64 panel. Inputs are numeric Form tables; output is a numeric Form.

Run `python -m operon registry build` after editing.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（2.71 s），导出 None 行，产物 sha256 6f78403bd8689041…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_singlecell_panel_b64.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/sc_leiden_cluster |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 2.71 s，导出 None 行。
- 归档路线：`/tmp/cov_omics/sc_leiden_cluster`。
- 命令：`/home/gavin/bp-numpy21/bin/python scripts/run.py /tmp/cov_omics/sc_leiden_cluster`。

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。

## 4. 限制与失败模式

相邻算子 Markdown 是参数约束与失败模式的权威说明；未找到单独的限制段。

## 5. 复现

```bash
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^sc_leiden_cluster,' verification/coverage-8.0.1/operator_coverage.csv
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
