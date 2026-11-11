# Pose RMSD to a reference (`vina_pose_rmsd`)

**Category:** Structure  
**Entry point:** `src.task.step.steps.vina_pose_rmsd:VinaPoseRmsdStep`  
**Source:** [`library/seed/src/task/step/steps/vina_pose_rmsd.py`](../../library/seed/src/task/step/steps/vina_pose_rmsd.py) (233 lines)  
**Trust level: D — 专用测试引用（无真实执行）**

## 1. 代码说明

Superpose every docked ligand pose onto a reference pose, matching symmetry-equivalent atoms, and report the RMSD and the largest per-atom

> Symmetry-aware RMSD between docked poses and a reference ligand

关键符号：

- `def pose_table() (line 31)`
- `def reference_table() (line 71)`
- `def rmsd_rows() (line 85)`
- `class VinaPoseRmsdStep (line 122)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=3, numeric=True, dims=(pose_dim, atom_dim, field_dim), info=(encoders)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `pose_dim` | `pose` | 位姿维度名 |
| `atom_dim` | `atom` | 原子维度名 |
| `field_dim` | `field` | 字段维度名 |
| `reference_path` | `` | 参考位姿 |
| `allow_symmetry` | `True` | 对称匹配 |
| `output` | `rmsd` | 输出 |

## 2. 用途与解释

Symmetry-aware RMSD between docked poses and a reference ligand pose.

Compare docked poses with a reference binding pose.

## 3. 正确性依据

**结论：D 级。** 只有专用/冒烟测试引用；没有记录真实执行。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension268.py |
| L3 真实执行 | SKIP | no route in audit, archive, or srv evidence |
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
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^vina_pose_rmsd,' verification/coverage-8.0.1/operator_coverage.csv
```

算子手册中的示例：

```text
Use the registry to discover compatible Readers and validate a complete workflow
before execution. This generated page does not claim an executable scientific
example. Add a tested example and replace this generated page with authored
guidance when extending this operator.
```

未补齐证据：`L3,L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
