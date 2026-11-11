# Docking pose clustering (`vina_pose_cluster`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.vina_pose_cluster:VinaPoseClusterStep`  
**Source:** [`library/seed/src/task/step/steps/vina_pose_cluster.py`](../../library/seed/src/task/step/steps/vina_pose_cluster.py) (204 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Cluster the poses returned by vina_dock with symmetry-aware heavy-atom RMSD and greedy leader clustering, reporting the cluster of every pose and the distance to its cluster

> Cluster docked poses by symmetry-aware heavy-atom

关键符号：

- `def pose_tables() (line 18)`
- `def cluster_tables() (line 58)`
- `class VinaPoseClusterStep (line 108)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=3, numeric=True, dims=(pose_dim, atom_dim, field_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `pose_dim` | `pose` | 构象维 |
| `atom_dim` | `atom` | 原子维 |
| `field_dim` | `field` | 字段维 |
| `cutoff` | `2.0` | 聚类阈值（Å）; min 0.1; max 20.0 |
| `allow_symmetry` | `True` | 对称匹配 |
| `output` | `clusters` | 输出名称 |

## 2. 用途与解释

Cluster docked poses by symmetry-aware heavy-atom RMSD.

Group docked poses into binding modes.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（0.4113 s），导出 None 行，产物 sha256 83e0b1e4118f1ccd…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension248.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/vina_pose_cluster |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 0.4113 s，导出 None 行。
- 归档路线：`/tmp/vina_routes/vina_pose_cluster`。
- 命令：``。

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
grep '^vina_pose_cluster,' verification/coverage-8.0.1/operator_coverage.csv
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
