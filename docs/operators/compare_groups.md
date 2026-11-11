# Group comparison (`compare_groups`)

**Category:** Analysis  
**Entry point:** `src.task.step.steps.compare_groups:CompareGroupsStep`  
**Source:** [`library/seed/src/task/step/steps/compare_groups.py`](../../library/seed/src/task/step/steps/compare_groups.py) (683 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

T-test、Welch、Mann–Whitney 或

> Compare groups along one dimension of a 2D form. Three modes ----------- two_groups compare group_a vs group_b (default, backward compatible with the original two-group API). Output dims: [dim, "statistic"]. one_vs_rest for every group g: g vs the union of all other groups. Output dims: [dim, "comparison", "statistic"], with one entry per group. pairwise every unordered pair (g_i, g_j). Output dims: [dim, "comparison", "statistic"]. Methods ------- ttest scipy.stats.ttest_ind(equal_var=True) welch scipy.stats.ttest_ind(equal_var=False) mannwhitney scipy.stats.mannwhitneyu deseq2 pydeseq2…

关键符号：

- `class CompareGroupsStep (line 80)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(dim, group_dim), info=(—)
- 输入 2: ndim=2, numeric=True, dims=(group_dim), info=(—)
- 输出: mode=compare_groups, schema={}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `dim` | `` | — |
| `group_dim` | `` | — |
| `group_label` | `` | — |
| `mode` | `two_groups` | choices: two_groups, one_vs_rest, pairwise |
| `group_a` | `` | — |
| `group_b` | `` | — |
| `groups` | `` | — |
| `min_per_group` | `2` | min 1 |
| `method` | `ttest` | choices: ttest, welch, mannwhitney, wilcoxon, deseq2 |

## 2. 用途与解释

Compare groups along one dimension of a 2D form.

Three modes
-----------
two_groups     compare group_a vs group_b (default, backward
compatible with the original two-group API).
Output dims: [dim, "statistic"].
one_vs_rest    for every group g: g vs the union of all other
groups. Output dims: [dim, "comparison",
"statistic"], with one entry per group.
pairwise       every unordered pair (g_i, g_j). Output dims:
[dim, "comparison", "statistic"].

Methods
-------
ttest        scipy.stats.ttest_ind(equal_var=True)
welch        scipy.stats.ttest_ind(equal_var=False)
mannwhitney  scipy.stats.mannwhitneyu
deseq2       pydeseq2 negative binomial GLM

The two-group output is a 2D form with columns log2FC, mean_a,
mean_b, stat, P, N. The multi-group output adds a "comparison"
axis between the feature axis and the statistic axis.

Consuming a multi-group result in a 2D pipeline requires selectin

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_axis_adapters.py,test_builtin_pins.py,test_packages.py,test_upstream_operators.py |
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
grep '^compare_groups,' verification/coverage-8.0.1/operator_coverage.csv
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
