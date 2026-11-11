# 自由能景观 (`structure_md_free_energy_landscape`)

**Category:** Structure  
**Entry point:** `src.task.step.steps.structure_md_free_energy_landscape:StructureMdFreeEnergyLandscapeStep`  
**Source:** [`library/seed/src/task/step/steps/structure_md_free_energy_landscape.py`](../../library/seed/src/task/step/steps/structure_md_free_energy_landscape.py) (128 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Project trajectory frames onto the two leading principal components and build a histogram-based free-energy landscape F = -kT ln

> structure_md_free_energy_landscape: 2D free-energy surface from PC

关键符号：

- `def project() (line 17)`
- `def free_energy() (line 28)`
- `class StructureMdFreeEnergyLandscapeStep (line 42)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": false}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `trajectory_path` | `` | 轨迹 .npy 路径 |
| `topology_path` | `` | 拓扑 PDB 路径 |
| `pc1` | `0` | PC1 索引; min 0; max 50 |
| `pc2` | `1` | PC2 索引; min 0; max 50 |
| `bins` | `20` | 直方图格数; min 2; max 100 |
| `temperature` | `300.0` | 温度（K）; min 1.0; max 1000.0 |
| `output` | `landscape` | 输出参数名 |

## 2. 用途与解释

structure_md_free_energy_landscape: 2D free-energy surface from PC projections.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（4.81 s），导出 None 行，产物 sha256 n/a…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension332.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/structure_md_free_energy_landscape |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 4.81 s，导出 None 行。
- 归档路线：`/tmp/cov_structure/structure_md_free_energy_landscape`。
- 命令：`python scripts/run.py /tmp/cov_structure/structure_md_free_energy_landscape`。

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
grep '^structure_md_free_energy_landscape,' verification/coverage-8.0.1/operator_coverage.csv
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
