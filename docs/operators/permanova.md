# PERMANOVA (`permanova`)

**Category:** 统计分析  
**Entry point:** `src.task.step.steps.permanova:PermanovaStep`  
**Source:** [`library/seed/src/task/step/steps/permanova.py`](../../library/seed/src/task/step/steps/permanova.py) (409 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

PERMANOVA on a distance matrix with a grouping

> PERMANOVA — permutation-based multivariate analysis of variance. Given a distance matrix (produced by ``distance_matrix``) and a group label for each sample, tests whether the between-group distances are larger than expected by chance. Two inputs share a sample dim. The first is a square distance matrix, the second carries the group column. Both must have the same labels on the sample dim. Method ------ Anderson (2001) PERMANOVA on a distance matrix: a_ij = d_ij^2 / 2 SS_T = sum over all i,j of a_ij, divided by n SS_W = sum_g (1/n_g) * sum over i,j in g of a_ij SS_A = SS_T - SS_W F = (SS_A /…

关键符号：

- `class PermanovaStep (line 68)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(dist_dim, dist_dim), info=(—)
- 输入 2: ndim=2, numeric=True, dims=(group_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "dims": ["comparison", "statistic"], "labels": {"comparison": null, "statistic": ["F", "R2", "P", "n_perm"]}, "axis_info": {}, "info": {"missing_code": {"type": ["number", "null"]}, "representation": {"type": "string", "const": "permanova"}}}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `dist_dim` | `sample` | — |
| `group_dim` | `` | — |
| `group_label` | `` | — |
| `groups` | `` | — |
| `pairwise` | `False` | — |
| `n_permutations` | `999` | min 1 |
| `random_state` | `0` | — |

## 2. 用途与解释

PERMANOVA — permutation-based multivariate analysis of variance.

Given a distance matrix (produced by ``distance_matrix``) and a
group label for each sample, tests whether the between-group
distances are larger than expected by chance.

Two inputs share a sample dim. The first is a square distance
matrix, the second carries the group column. Both must have the
same labels on the sample dim.

Method
------
Anderson (2001) PERMANOVA on a distance matrix:

a_ij    = d_ij^2 / 2
SS_T    = sum over all i,j of a_ij, divided by n
SS_W    = sum_g (1/n_g) * sum over i,j in g of a_ij
SS_A    = SS_T - SS_W
F       = (SS_A / (g-1)) / (SS_W / (n-g))
R^2     = SS_A / SS_T
p-value = fraction of permutations with F >= F_obs

Two modes
---------
overall     one test across all groups (default)
pairwise    one test per unordered pair of groups, in addition
to the overall test

Output
------
dims    = ["co

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_microbiome.py |
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
grep '^permanova,' verification/coverage-8.0.1/operator_coverage.csv
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
