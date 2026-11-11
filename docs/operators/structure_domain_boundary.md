# Structure domain boundary (`structure_domain_boundary`)

**Category:** Structure  
**Entry point:** `src.task.step.steps.structure_domain_boundary:StructureDomainBoundaryStep`  
**Source:** [`library/seed/src/task/step/steps/structure_domain_boundary.py`](../../library/seed/src/task/step/steps/structure_domain_boundary.py) (312 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Segment a chain into domains from the CA contact graph (connected components or normalized-Laplacian spectral clustering) and report each residue's domain, the number of cross-domain contacts and whether it sits on a domain

> Domain boundaries from the CA contact graph. Two residues are in contact when their CA atoms are within ``contact_cutoff`` angstrom and at least ``min_separation`` positions apart. Disconnected graphs give their connected components directly; connected graphs are split with a spectral clustering whose cluster count comes from the normalized-Laplacian eigengap. Residues whose contacts cross a domain border mark the

关键符号：

- `def ca_adjacency() (line 22)`
- `def connected_components() (line 33)`
- `def normalized_laplacian() (line 56)`
- `def eigengap_domains() (line 69)`
- `def kmeans_embedding() (line 92)`
- `def spectral_domains() (line 125)`
- `def domain_assignment() (line 142)`
- `def boundary_rows() (line 169)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(atom_dim, field_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `atom_dim` | `atom` | 原子维度名; advanced |
| `field_dim` | `field` | 字段维度名; advanced |
| `residue_dim` | `residue` | 残基维度名; advanced |
| `contact_cutoff` | `8.0` | CA 接触距离阈值 (Å); min 4.0; max 15.0 |
| `min_separation` | `3` | 最小序列间隔; min 1; max 100 |
| `n_domains` | `0` | 结构域数（0=自动）; min 0; max 8 |
| `max_domains` | `4` | 自动检测的最大结构域数; min 2; max 8; advanced |
| `min_gap_ratio` | `1.5` | 特征间隙比阈值; min 1.0; max 10.0; advanced |
| `seed` | `0` | 随机种子; advanced |
| `output` | `domains` | 输出名称 |

## 2. 用途与解释

Domain boundaries from the CA contact graph.

Two residues are in contact when their CA atoms are within ``contact_cutoff``
angstrom and at least ``min_separation`` positions apart.  Disconnected graphs
give their connected components directly; connected graphs are split with a
spectral clustering whose cluster count comes from the normalized-Laplacian
eigengap.  Residues whose contacts cross a domain border mark the boundary.

Split a CA contact graph into domains and flag the boundary residues.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension238.py |
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
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^structure_domain_boundary,' verification/coverage-8.0.1/operator_coverage.csv
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
