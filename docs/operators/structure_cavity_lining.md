# Cavity lining residues (`structure_cavity_lining`)

**Category:** Structure  
**Entry point:** `src.task.step.steps.structure_cavity_lining:StructureCavityLiningStep`  
**Source:** [`library/seed/src/task/step/steps/structure_cavity_lining.py`](../../library/seed/src/task/step/steps/structure_cavity_lining.py) (252 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Residues lining the largest buried cavity of a structure, with their nearest distance to the cavity

> Residues lining the largest buried cavity of a PDB structure form. The structure is rasterised onto a regular grid (see ``structure_cavity_scan``); free cells unreachable from the box boundary form buried cavities. The largest cavity by volume is selected and every residue with a heavy atom within ``lining_cutoff`` of a cavity cell centre is

关键符号：

- `def cavity_cells() (line 38)`
- `def lining_rows() (line 58)`
- `class StructureCavityLiningStep (line 80)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(atom_dim, field_dim), info=(encoders)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `atom_dim` | `atom` | 原子维度; advanced |
| `field_dim` | `field` | 字段维度; advanced |
| `residue_dim` | `residue` | 残基维度; advanced |
| `spacing` | `1.0` | 网格间距; max 4.0; advanced |
| `probe_radius` | `1.4` | 探测半径; max 5.0; advanced |
| `min_volume` | `20.0` | 最小空腔体积; min 0.0 |
| `padding` | `2.0` | 边界填充; min 0.0; max 10.0; advanced |
| `lining_cutoff` | `4.0` | 衬里距离截断; max 12.0 |
| `output` | `lining` | 输出名称; advanced |

## 2. 用途与解释

Residues lining the largest buried cavity of a PDB structure form.

The structure is rasterised onto a regular grid (see ``structure_cavity_scan``);
free cells unreachable from the box boundary form buried cavities.  The largest
cavity by volume is selected and every residue with a heavy atom within
``lining_cutoff`` of a cavity cell centre is reported.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension230.py |
| L3 真实执行 | ROUTE | operator_table.csv:generated_route |
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
cd /path/to/Operon-worktree
python -m operon registry check --json
grep '^structure_cavity_lining,' verification/coverage-8.0.1/operator_coverage.csv
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
