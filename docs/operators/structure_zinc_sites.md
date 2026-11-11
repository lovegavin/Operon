# Structural zinc sites (`structure_zinc_sites`)

**Category:** Structure  
**Entry point:** `src.task.step.steps.structure_zinc_sites:StructureZincSitesStep`  
**Source:** [`library/seed/src/task/step/steps/structure_zinc_sites.py`](../../library/seed/src/task/step/steps/structure_zinc_sites.py) (256 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Find zinc ions in a PDB atom table and report the cysteine and histidine atoms within coordination distance, with ligand counts and Zn-donor

> Zinc coordination sites in a PDB structure form. A structural zinc site is a zinc ion surrounded by cysteine thiolates and histidine imidazole nitrogens at bonding distance. The operator scans the heavy-atom table for zinc atoms, collects protein S/N donors within the coordination cutoff, and reports one row per site with the ligand count and the mean and minimum Zn-donor

关键符号：

- `def atom_labels() (line 34)`
- `def zinc_sites() (line 49)`
- `class StructureZincSitesStep (line 106)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(atom_dim, field_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `atom_dim` | `atom` | 原子维度 |
| `field_dim` | `field` | 字段维度 |
| `coordination_cutoff` | `2.9` | 配位距离上限; min 1.5; max 4.0 |
| `min_ligands` | `3` | 最少配体数; min 1; max 8 |
| `output` | `sites` | 输出名称 |

## 2. 用途与解释

Zinc coordination sites in a PDB structure form.

A structural zinc site is a zinc ion surrounded by cysteine thiolates and
histidine imidazole nitrogens at bonding distance.  The operator scans the
heavy-atom table for zinc atoms, collects protein S/N donors within the
coordination cutoff, and reports one row per site with the ligand count and the
mean and minimum Zn-donor distance.

Structural zinc sites from Cys/His coordination geometry.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（1.5 s），导出 None 行，产物 sha256 n/a…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension235.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/structure_zinc_sites |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 1.5 s，导出 None 行。
- 归档路线：`/tmp/cov_structure/structure_zinc_sites`。
- 命令：`/home/gavin/bp-numpy21/bin/python scripts/run.py /tmp/cov_structure/structure_zinc_sites`。

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
grep '^structure_zinc_sites,' verification/coverage-8.0.1/operator_coverage.csv
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
