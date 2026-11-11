# MD 氢键占有率 (`structure_md_hbond_occupancy`)

**Category:** Structure  
**Entry point:** `src.task.step.steps.structure_md_hbond_occupancy:StructureMdHbondOccupancyStep`  
**Source:** [`library/seed/src/task/step/steps/structure_md_hbond_occupancy.py`](../../library/seed/src/task/step/steps/structure_md_hbond_occupancy.py) (230 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Detect donor-H...acceptor hydrogen bonds from topology and per-frame geometry, and report the fraction of MD frames in which each residue pair stays

> structure_md_hbond_occupancy: hydrogen-bond persistence along a

关键符号：

- `def load_frames() (line 17)`
- `def parse_atoms() (line 27)`
- `def donor_hydrogens() (line 42)`
- `def candidate_bonds() (line 63)`
- `def hbond_geometry() (line 78)`
- `def occupancy_rows() (line 92)`
- `class StructureMdHbondOccupancyStep (line 121)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": false}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `trajectory_path` | `` | 轨迹文件 (.npy, nm) |
| `topology_path` | `` | 拓扑 PDB（含氢） |
| `chains` | `` | 链过滤（逗号分隔） |
| `cutoff` | `3.5` | H...受体距离 (Å); min 1.5; max 6.0 |
| `angle_cutoff` | `120.0` | D-H...A 角度下限 (°); min 60.0; max 180.0 |
| `min_occupancy` | `0.2` | 最小占有率; min 0.0; max 1.0 |
| `stride` | `1` | 采样间隔（帧）; min 1; max 100 |
| `bond_dim` | `hbond` | 输出维度名 |
| `output` | `hbonds` | 输出参数名 |

## 2. 用途与解释

structure_md_hbond_occupancy: hydrogen-bond persistence along a trajectory.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（106.97 s），导出 None 行，产物 sha256 n/a…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension320.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/structure_md_hbond_occupancy |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 106.97 s，导出 None 行。
- 归档路线：`/tmp/cov_structure/structure_md_hbond_occupancy`。
- 命令：`python scripts/run.py /tmp/cov_structure/structure_md_hbond_occupancy`。

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
grep '^structure_md_hbond_occupancy,' verification/coverage-8.0.1/operator_coverage.csv
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
