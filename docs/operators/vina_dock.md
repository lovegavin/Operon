# AutoDock Vina docking (`vina_dock`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.vina_dock:VinaDockStep`  
**Source:** [`library/seed/src/task/step/steps/vina_dock.py`](../../library/seed/src/task/step/steps/vina_dock.py) (354 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Run AutoDock Vina with a PDBQT receptor and ligand, then return every docked pose as a [pose, atom, field] table together with the affinity table parsed from the Vina

> Molecular docking with the official AutoDock Vina command

关键符号：

- `def element_of() (line 31)`
- `def parse_vina_log() (line 49)`
- `def parse_poses() (line 72)`
- `def ligand_centroid() (line 135)`
- `def docking_command() (line 142)`
- `def stack_poses() (line 183)`
- `class VinaDockStep (line 221)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 3, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `receptor_path` | `` | 受体 PDBQT |
| `ligand_path` | `` | 配体 PDBQT |
| `auto_center` | `True` | 自动居中 |
| `center_x` | `0.0` | 中心 X |
| `center_y` | `0.0` | 中心 Y |
| `center_z` | `0.0` | 中心 Z |
| `size_x` | `20.0` | 盒子 X; min 5.0; max 60.0 |
| `size_y` | `20.0` | 盒子 Y; min 5.0; max 60.0 |
| `size_z` | `20.0` | 盒子 Z; min 5.0; max 60.0 |
| `num_modes` | `9` | 构象数; min 1; max 50 |
| `exhaustiveness` | `8` | 搜索强度; min 1; max 64 |
| `seed` | `42` | 随机种子; min 0; max 2147483647 |
| `vina_path` | `vina` | Vina 可执行文件 |
| `timeout_seconds` | `1800` | 超时（秒）; min 60; max 86400 |
| `output` | `pose` | 输出名称 |

## 2. 用途与解释

Molecular docking with the official AutoDock Vina command line.

Dock one ligand into a receptor with AutoDock Vina.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（0.3985 s），导出 None 行，产物 sha256 83e0b1e4118f1ccd…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension247.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/vina_dock |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 0.3985 s，导出 None 行。
- 归档路线：`/tmp/vina_routes/vina_dock`。
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
grep '^vina_dock,' verification/coverage-8.0.1/operator_coverage.csv
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
