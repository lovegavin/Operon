# Most recent common ancestor of two tips (`tree_mrca`)

**Category:** Phylogenetics  
**Entry point:** `src.task.step.steps.tree_mrca:TreeMrcaStep`  
**Source:** [`library/seed/src/task/step/steps/tree_mrca.py`](../../library/seed/src/task/step/steps/tree_mrca.py) (80 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Finds the MRCA node of two tip labels in a Newick tree and reports its height and pairwise

> Operon operator

关键符号：

- `class TreeMrcaStep (line 7)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `output` | `output` | Output name |
| `newick` | `(A:1,B:1);` | Newick tree |
| `taxon_a` | `` | taxon a |
| `taxon_b` | `` | taxon b |

## 2. 用途与解释

Finds the MRCA node of two tip labels in a Newick tree and reports its height and pairwise distance.

Inputs are tree parameters (Newick string) and, where relevant, a numerical matrix.
The output is a two-dimensional form with the reported statistics.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（1.44 s），导出 1 行，产物 sha256 14128e6cbba3c2fa…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_tree_panel_b72.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/tree_mrca |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 1.44 s，导出 1 行。
- 归档路线：`/tmp/cov_stats/tree_mrca`。
- 命令：`cd /home/gavin/Operon && /home/gavin/bp-numpy21/bin/python scripts/run.py /tmp/cov_stats/tree_mrca --check && /home/gavin/bp-numpy21/bin/python scripts/run.py /tmp/cov_stats/tree_mrca`。

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。

## 4. 限制与失败模式

Newick parsing supports rooted trees with branch lengths; support values and quoted labels are not interpreted.

## 5. 复现

```bash
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^tree_mrca,' verification/coverage-8.0.1/operator_coverage.csv
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
