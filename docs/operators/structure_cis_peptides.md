# Cis peptide bonds from omega dihedrals (`structure_cis_peptides`)

**Category:** Structure  
**Entry point:** `src.task.step.steps.structure_cis_peptides:StructureCisPeptidesStep`  
**Source:** [`library/seed/src/task/step/steps/structure_cis_peptides.py`](../../library/seed/src/task/step/steps/structure_cis_peptides.py) (179 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Computes the backbone omega dihedral of every consecutive peptide bond and flags bonds whose absolute angle is below the cis threshold. Bonds across missing-residue gaps are

> Cis peptide bonds from backbone omega dihedrals. Input: a PDB Form (``dims=[atom, field]``) as produced by ``PdbReader``. Output: 2D Form ``[bond, statistic]`` with ``omega``, ``abs_omega`` and an ``is_cis`` flag for every consecutive peptide bond of each chain. A bond is classified as cis when ``abs(omega) <= cis_threshold`` degrees (default 30). Bonds that span a residue-numbering gap carry no peptide bond and are

关键符号：

- `def cis_peptide_rows() (line 25)`
- `class StructureCisPeptidesStep (line 60)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(atom_dim, field_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `atom_dim` | `atom` | 原子维度 |
| `field_dim` | `field` | 字段维度 |
| `bond_dim` | `bond` | 肽键维度 |
| `cis_threshold` | `30.0` | 顺式阈值（度）; min 0.0; max 90.0 |
| `chain` | `` | 限定链; advanced |
| `output` | `cis_peptides` | 输出参数; advanced |

## 2. 用途与解释

Cis peptide bonds from backbone omega dihedrals.

Input: a PDB Form (``dims=[atom, field]``) as produced by ``PdbReader``.
Output: 2D Form ``[bond, statistic]`` with ``omega``, ``abs_omega`` and an
``is_cis`` flag for every consecutive peptide bond of each chain.

A bond is classified as cis when ``abs(omega) <= cis_threshold`` degrees
(default 30).  Bonds that span a residue-numbering gap carry no peptide bond
and are skipped.

Measure omega dihedrals and flag cis peptide bonds.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension367.py |
| L3 真实执行 | ROUTE | operator_table.csv:builtin_route |
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
grep '^structure_cis_peptides,' verification/coverage-8.0.1/operator_coverage.csv
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
