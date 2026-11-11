# OpenMM potential energy (`structure_openmm_energy`)

**Category:** Structure  
**Entry point:** `src.task.step.steps.structure_openmm_energy:StructureOpenmmEnergyStep`  
**Source:** [`library/seed/src/task/step/steps/structure_openmm_energy.py`](../../library/seed/src/task/step/steps/structure_openmm_energy.py) (225 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Build an OpenMM system for a protein structure and report the potential energy, optionally

> OpenMM potential energy and energy minimization for a protein

关键符号：

- `def structure_columns() (line 18)`
- `def write_pdb() (line 24)`
- `def gradient_norm() (line 65)`
- `def energy_terms() (line 70)`
- `def run_openmm() (line 76)`
- `class StructureOpenmmEnergyStep (line 123)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(atom_dim, field_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": false}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `atom_dim` | `atom` | 原子维度 |
| `field_dim` | `field` | 字段维度 |
| `forcefield` | `amber14-all.xml` | 力场文件 |
| `implicit_model` | `implicit/gbn2.xml` | 隐式溶剂 |
| `ph` | `7.0` | 质子化 pH; min 0.1; max 13.9 |
| `minimize` | `True` | 执行最小化 |
| `max_iterations` | `300` | 最小化迭代上限; min 1; max 100000 |
| `tolerance` | `10.0` | 收敛容差 kJ/mol/nm; min 0.001; max 10000.0 |
| `stage_dim` | `stage` | 阶段维度 |
| `output` | `energy` | 输出参数 |

## 2. 用途与解释

OpenMM potential energy and energy minimization for a protein structure.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（27.99 s），导出 None 行，产物 sha256 n/a…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension295.py,test_remote_provision.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/structure_openmm_energy |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 27.99 s，导出 None 行。
- 归档路线：`/tmp/cov_structure/structure_openmm_energy`。
- 命令：`python scripts/run.py /tmp/cov_structure/structure_openmm_energy`。

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
grep '^structure_openmm_energy,' verification/coverage-8.0.1/operator_coverage.csv
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
