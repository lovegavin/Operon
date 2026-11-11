# Batch docking (`vina_dock_batch`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.vina_dock_batch:VinaDockBatchStep`  
**Source:** [`library/seed/src/task/step/steps/vina_dock_batch.py`](../../library/seed/src/task/step/steps/vina_dock_batch.py) (252 lines)  
**Trust level: D — 专用测试引用（无真实执行）**

## 1. 代码说明

Run AutoDock Vina for every listed PDBQT ligand against one receptor and report the best affinity, RMSD bounds and mode count per

> Dock several ligands against one receptor with AutoDock

关键符号：

- `def split_paths() (line 22)`
- `def unique_labels() (line 29)`
- `def run_ligand() (line 50)`
- `class VinaDockBatchStep (line 106)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `receptor_path` | `` | 受体文件 |
| `ligand_paths` | `` | 配体列表 |
| `vina_path` | `vina` | Vina 可执行文件 |
| `center_x` | `` | 中心 X; min -1000.0; max 1000.0 |
| `center_y` | `` | 中心 Y; min -1000.0; max 1000.0 |
| `center_z` | `` | 中心 Z; min -1000.0; max 1000.0 |
| `size_x` | `20.0` | 盒长 X; min 5.0; max 100.0 |
| `size_y` | `20.0` | 盒长 Y; min 5.0; max 100.0 |
| `size_z` | `20.0` | 盒长 Z; min 5.0; max 100.0 |
| `num_modes` | `9` | 模式数; min 1; max 50 |
| `exhaustiveness` | `8` | 穷举度; min 1; max 64 |
| `seed` | `0` | 随机种子; min 0; max 2147483647 |
| `timeout_seconds` | `600` | 超时; min 1; max 86400 |
| `output` | `results` | 输出名 |

## 2. 用途与解释

Dock several ligands against one receptor with AutoDock Vina.

Dock a list of PDBQT ligands and rank their best affinities.

## 3. 正确性依据

**结论：D 级。** 只有专用/冒烟测试引用；没有记录真实执行。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension259.py,test_extension357.py |
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
grep '^vina_dock_batch,' verification/coverage-8.0.1/operator_coverage.csv
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
