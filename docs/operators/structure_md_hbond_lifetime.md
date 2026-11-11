# 氢键寿命 (`structure_md_hbond_lifetime`)

**Category:** Structure  
**Entry point:** `src.task.step.steps.structure_md_hbond_lifetime:StructureMdHbondLifetimeStep`  
**Source:** [`library/seed/src/task/step/steps/structure_md_hbond_lifetime.py`](../../library/seed/src/task/step/steps/structure_md_hbond_lifetime.py) (206 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Detect hydrogen bonds per frame and report residence statistics: occupancy, mean and maximum continuous lifetime, transitions and picosecond

> structure_md_hbond_lifetime: hydrogen-bond residence times along a

关键符号：

- `def presence_matrix() (line 21)`
- `def run_lengths() (line 44)`
- `def lifetime_rows() (line 60)`
- `class StructureMdHbondLifetimeStep (line 98)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": false}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `trajectory_path` | `` | 轨迹 .npy 路径 |
| `topology_path` | `` | 拓扑 PDB 路径 |
| `frame_time_ps` | `0.2` | 帧间隔（ps）; min 0.001; max 100.0 |
| `min_occupancy` | `0.5` | 最小占据率; min 0.0; max 1.0 |
| `max_distance` | `3.5` | H···A 最大距离（Å）; min 2.0; max 5.0 |
| `min_angle` | `120.0` | 最小 D-H···A 角度（°）; min 90.0; max 180.0 |
| `n_pairs` | `20` | 输出对数; min 1; max 500 |
| `output` | `lifetimes` | 输出参数名 |

## 2. 用途与解释

structure_md_hbond_lifetime: hydrogen-bond residence times along a trajectory.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（424.31 s），导出 None 行，产物 sha256 n/a…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension335.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/structure_md_hbond_lifetime |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 424.31 s，导出 None 行。
- 归档路线：`/tmp/cov_structure/structure_md_hbond_lifetime`。
- 命令：`python scripts/run.py /tmp/cov_structure/structure_md_hbond_lifetime`。

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
grep '^structure_md_hbond_lifetime,' verification/coverage-8.0.1/operator_coverage.csv
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
