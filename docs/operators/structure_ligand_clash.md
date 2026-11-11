# Ligand steric clashes (`structure_ligand_clash`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.structure_ligand_clash:StructureLigandClashStep`  
**Source:** [`library/seed/src/task/step/steps/structure_ligand_clash.py`](../../library/seed/src/task/step/steps/structure_ligand_clash.py) (195 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Count van der Waals overlaps between ligand heavy atoms and protein heavy atoms, with per-atom worst overlap and closest

> Report steric clashes between ligand heavy atoms and protein heavy

关键符号：

- `def atom_table() (line 30)`
- `def heavy_mask() (line 42)`
- `def clash_rows() (line 47)`
- `class StructureLigandClashStep (line 68)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(atom_dim, field_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `atom_dim` | `atom` | 原子维度 |
| `field_dim` | `field` | 字段维度 |
| `atom_labels_dim` | `ligand_atom` | 配体原子维度; advanced |
| `ligand_resnames` | `LIG` | 配体残基名 |
| `tolerance` | `0.4` | 重叠容差（Å）; min 0.0; max 2.0 |
| `clash_scale` | `1.0` | 范德华半径缩放; min 0.5; max 1.5; advanced |
| `output` | `clashes` | 输出名; advanced |

## 2. 用途与解释

Report steric clashes between ligand heavy atoms and protein heavy atoms.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（0 s），导出 0 行，产物 sha256 n/a…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension212.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/structure_ligand_clash |
| L4 资源 | SKIP | no memory estimate |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 0 s，导出 0 行。
- 归档路线：`verification/coverage-8.0.1/routes/structure_ligand_clash`。
- 命令：`scripts/run.py <archived route>`。

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
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^structure_ligand_clash,' verification/coverage-8.0.1/operator_coverage.csv
```

算子手册中的示例：

```text
Use the registry to discover compatible Readers and validate a complete workflow
before execution. This generated page does not claim an executable scientific
example. Add a tested example and replace this generated page with authored
guidance when extending this operator.
```

未补齐证据：`L4`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
