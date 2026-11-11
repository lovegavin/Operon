# Cell cycle score (`cell_cycle_score`)

**Category:** Omics  
**Entry point:** `src.task.step.steps.cell_cycle_score:CellCycleScoreStep`  
**Source:** [`library/seed/src/task/step/steps/cell_cycle_score.py`](../../library/seed/src/task/step/steps/cell_cycle_score.py) (108 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Cell cycle score：接收 2 个输入，输出 Form；主要参数：Cell Dim、Gene Dim、Gene Set Dim、Ctrl Size、N

> Cell-cycle S/G2M scores and phase assignment (Scanpy

关键符号：

- `class CellCycleScoreStep (line 13)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(cell_dim, gene_dim), info=(—)
- 输入 2: ndim=2, numeric=True, dims=(gene_dim, gene_set_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": false}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `cell_dim` | `cell` | Cell Dim |
| `gene_dim` | `gene` | Gene Dim |
| `gene_set_dim` | `gene_set` | Gene Set Dim |
| `ctrl_size` | `50` | Ctrl Size; min 1 |
| `n_bins` | `25` | N Bins; min 1 |
| `random_state` | `0` | 随机种子; advanced |
| `output` | `` | 输出名称 |

## 2. 用途与解释

Cell-cycle S/G2M scores and phase assignment (Scanpy score_genes).

## 3. 正确性依据

**结论：B 级。** 真实运行通过（5.13 s），导出 None 行，产物 sha256 9648865e8a882243…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension11.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/cell_cycle_score |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 5.13 s，导出 None 行。
- 归档路线：`/tmp/cov_omics/cell_cycle_score`。
- 命令：`/home/gavin/bp-numpy21/bin/python scripts/run.py /tmp/cov_omics/cell_cycle_score`。

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
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^cell_cycle_score,' verification/coverage-8.0.1/operator_coverage.csv
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
