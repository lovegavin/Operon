# OpenMM 短程分子动力学稳定性 (`structure_openmm_md_stability`)

**Category:** Structure  
**Entry point:** `src.task.step.steps.structure_openmm_md_stability:StructureOpenmmMdStabilityStep`  
**Source:** [`library/seed/src/task/step/steps/structure_openmm_md_stability.py`](../../library/seed/src/task/step/steps/structure_openmm_md_stability.py) (257 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Minimise an implicit-solvent system with OpenMM and run a short Langevin trajectory, reporting temperature, potential energy, RMSD and radius of gyration per sampled

> structure_openmm_md_stability: short implicit-solvent MD with drift

关键符号：

- `def radius_of_gyration() (line 34)`
- `def temperature_from_kinetic() (line 41)`
- `def without_water() (line 48)`
- `def drift_rows() (line 62)`
- `def drift_summary() (line 71)`
- `def md_run() (line 87)`
- `class StructureOpenmmMdStabilityStep (line 164)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(atom_dim, field_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": false}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `atom_dim` | `atom` | 原子维度名 |
| `field_dim` | `field` | 字段维度名 |
| `ph` | `7.0` | 质子化 pH; min 0.0; max 14.0 |
| `temperature` | `300.0` | 温度 (K); min 250.0; max 450.0 |
| `friction` | `1.0` | Langevin 摩擦系数 (1/ps); min 0.1; max 50.0 |
| `step_size_fs` | `2.0` | 步长 (fs); min 0.5; max 4.0 |
| `steps` | `500` | 积分步数; min 10; max 200000 |
| `sample_every` | `50` | 采样间隔 (步); min 1; max 10000 |
| `minimize_iterations` | `500` | 能量最小化迭代上限; min 0; max 100000 |
| `seed` | `0` | 随机种子; min 0; max 1000000 |
| `forcefield` | `amber14-all.xml,implicit/gbn2.xml` | 力场文件（逗号分隔） |
| `frame_dim` | `frame` | 帧维度名 |
| `output` | `frames` | 输出参数名 |
| `remove_water` | `True` | 去除水分子 |
| `equilibrate_steps` | `500` | 预平衡步数; min 0; max 100000 |

## 2. 用途与解释

structure_openmm_md_stability: short implicit-solvent MD with drift statistics.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（44.41 s），导出 None 行，产物 sha256 n/a…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension299.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/structure_openmm_md_stability |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 44.41 s，导出 None 行。
- 归档路线：`/tmp/cov_structure/structure_openmm_md_stability`。
- 命令：`python scripts/run.py /tmp/cov_structure/structure_openmm_md_stability`。

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
grep '^structure_openmm_md_stability,' verification/coverage-8.0.1/operator_coverage.csv
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
