# AutoDock Vina 对接 (Python 绑定) (`vina_dock_python`)

**Category:** Docking  
**Entry point:** `src.task.step.steps.vina_dock_python:VinaDockPythonStep`  
**Source:** [`library/seed/src/task/step/steps/vina_dock_python.py`](../../library/seed/src/task/step/steps/vina_dock_python.py) (265 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Dock a prepared ligand PDBQT into a protein receptor with the official AutoDock Vina Python engine and report the per-pose scoring

> vina_dock_python: AutoDock Vina through its official Python

关键符号：

- `def ad4_type() (line 39)`
- `def receptor_pdbqt() (line 48)`
- `def parse_ligand_box() (line 76)`
- `def dock() (line 91)`
- `class VinaDockPythonStep (line 147)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(atom_dim, field_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": false}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `atom_dim` | `atom` | 原子维度名 |
| `field_dim` | `field` | 字段维度名 |
| `ligand_path` | `` | 配体 PDBQT 路径 |
| `center_x` | `0.0` | 盒中心 X（0=配体中心） |
| `center_y` | `0.0` | 盒中心 Y |
| `center_z` | `0.0` | 盒中心 Z |
| `size_x` | `20.0` | 盒尺寸 X (Å); min 5.0; max 100.0 |
| `size_y` | `20.0` | 盒尺寸 Y (Å); min 5.0; max 100.0 |
| `size_z` | `20.0` | 盒尺寸 Z (Å); min 5.0; max 100.0 |
| `exhaustiveness` | `8` | 穷举度; min 1; max 64 |
| `num_modes` | `9` | 输出姿态数; min 1; max 100 |
| `seed` | `42` | 随机种子; min 0; max 2147483647 |
| `cpu` | `1` | CPU 线程; min 1; max 32 |
| `scoring` | `vina` | 打分函数; choices: vina, vinardo |
| `pose_dim` | `pose` | 输出维度名 |
| `output` | `docking` | 输出参数名 |
| `flex_path` | `` | 柔性残基 PDBQT 路径（可选） |

## 2. 用途与解释

vina_dock_python: AutoDock Vina through its official Python bindings.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（5.25 s），导出 None 行，产物 sha256 f14580d98252ac75…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension312.py,test_extension313.py,test_extension357.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/vina_dock_python |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 5.25 s，导出 None 行。
- 归档路线：`/tmp/cov_structure/vina_dock_python`。
- 命令：`python scripts/run.py /tmp/cov_structure/vina_dock_python`。

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
grep '^vina_dock_python,' verification/coverage-8.0.1/operator_coverage.csv
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
