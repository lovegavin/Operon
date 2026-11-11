# Robinson-Foulds distance (`robinson_foulds`)

**Category:** Omics  
**Entry point:** `src.task.step.steps.robinson_foulds:RobinsonFouldsStep`  
**Source:** [`library/seed/src/task/step/steps/robinson_foulds.py`](../../library/seed/src/task/step/steps/robinson_foulds.py) (165 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Unweighted Robinson-Foulds distance between two node x field

> Unweighted Robinson-Foulds distance between two trees. Both inputs use the node x field encoding produced by the tree readers (parent / branch_length / depth / is_leaf). The operator rebuilds each topology with ``load_tree``, extracts the nontrivial bipartitions (splits), canonically represents each split by its smaller side, and reports the symmetric difference: rf |splits(A) XOR splits(B)| max_rf |splits(A)| + |splits(B)| normalized rf / max_rf (0 when both trees have no nontrivial split) The statistics match ``dendropy.calculate.treecompare. unweighted_robinson_foulds_distance`` for…

关键符号：

- `class RobinsonFouldsStep (line 27)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(node_dim, field_dim), info=(—)
- 输入 2: ndim=2, numeric=True, dims=(node_dim_b, field_dim_b), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `node_dim` | `node` | Tree A Node Dim |
| `field_dim` | `field` | Tree A Field Dim |
| `node_dim_b` | `node` | Tree B Node Dim |
| `field_dim_b` | `field` | Tree B Field Dim |
| `output` | `` | 输出名称 |

## 2. 用途与解释

Unweighted Robinson-Foulds distance between two trees.

Both inputs use the node x field encoding produced by the tree readers
(parent / branch_length / depth / is_leaf). The operator rebuilds each
topology with ``load_tree``, extracts the nontrivial bipartitions
(splits), canonically represents each split by its smaller side, and
reports the symmetric difference:

rf            |splits(A) XOR splits(B)|
max_rf        |splits(A)| + |splits(B)|
normalized    rf / max_rf (0 when both trees have no nontrivial split)

The statistics match ``dendropy.calculate.treecompare.
unweighted_robinson_foulds_distance`` for unrooted topologies, with
trivial splits (size 1 and n - 1) excluded.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（1.89 s），导出 None 行，产物 sha256 55539c7b0462923e…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension379.py,test_extension90.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/robinson_foulds |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 1.89 s，导出 None 行。
- 归档路线：`/tmp/cov_omics/robinson_foulds`。
- 命令：`/home/gavin/bp-numpy21/bin/python scripts/run.py /tmp/cov_omics/robinson_foulds`。

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
grep '^robinson_foulds,' verification/coverage-8.0.1/operator_coverage.csv
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
