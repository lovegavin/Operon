# Neighbor joining tree (`neighbor_joining`)

**Category:** Omics  
**Entry point:** `src.task.step.steps.neighbor_joining:NeighborJoiningStep`  
**Source:** [`library/seed/src/task/step/steps/neighbor_joining.py`](../../library/seed/src/task/step/steps/neighbor_joining.py) (127 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Neighbor-joining tree from a symmetric pairwise distance

> Neighbor-joining tree from a pairwise distance matrix. The topology and branch lengths follow the Saitou-Nei neighbor-joining algorithm: at each step the pair minimizing ``(m - 2) * d(i, j) - r(i) - r(j)`` is joined, with limb lengths ``d(i, j) / 2 + (r(i) - r(j)) / (2 * (m - 2))`` and ``d(i, j) - limb``. The final two clusters are attached to a synthetic root with half of their remaining distance. The result is a ``node x field`` table in the same encoding used by the Newick reader (parent / branch_length / depth / is_leaf), so it can be consumed by the tree operators such as patristic…

关键符号：

- `class NeighborJoiningStep (line 24)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(taxon_dim, taxon_b_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `taxon_dim` | `taxon` | Taxon Dim |
| `taxon_b_dim` | `taxon_b` | Taxon Dim B |
| `node_dim` | `node` | Node Dim; advanced |
| `field_dim` | `field` | Field Dim; advanced |
| `output` | `` | 输出名称 |

## 2. 用途与解释

Neighbor-joining tree from a pairwise distance matrix.

The topology and branch lengths follow the Saitou-Nei neighbor-joining
algorithm: at each step the pair minimizing
``(m - 2) * d(i, j) - r(i) - r(j)`` is joined, with limb lengths
``d(i, j) / 2 + (r(i) - r(j)) / (2 * (m - 2))`` and ``d(i, j) - limb``.
The final two clusters are attached to a synthetic root with half of
their remaining distance.

The result is a ``node x field`` table in the same encoding used by the
Newick reader (parent / branch_length / depth / is_leaf), so it can be
consumed by the tree operators such as patristic distance.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（2.11 s），导出 None 行，产物 sha256 1700689f5ef236cb…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension379.py,test_extension90.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/neighbor_joining |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 2.11 s，导出 None 行。
- 归档路线：`/tmp/cov_omics/neighbor_joining`。
- 命令：`python scripts/run.py /tmp/cov_omics/neighbor_joining`。

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
grep '^neighbor_joining,' verification/coverage-8.0.1/operator_coverage.csv
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
