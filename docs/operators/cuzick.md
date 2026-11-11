# Cuzick's trend test (`cuzick`)

**Category:** Statistics  
**Entry point:** `src.task.step.steps.cuzick:CuzickTestStep`  
**Source:** [`library/seed/src/task/step/steps/cuzick.py`](../../library/seed/src/task/step/steps/cuzick.py) (163 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Rank-based test for a monotone trend across ordered

> Cuzick's test for an ordered trend across

关键符号：

- `class CuzickTestStep (line 14)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(feature_dim, sample_dim), info=(—)
- 输入 2: ndim=2, numeric=True, dims=(sample_dim, group_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `feature_dim` | `feature` | Feature dimension |
| `sample_dim` | `sample` | Sample dimension |
| `group_dim` | `sample` | Metadata sample dimension |
| `group_label` | `group` | Group column |
| `group_order` | `` | Group order |
| `scores` | `` | Group scores |
| `alternative` | `two-sided` | Alternative; choices: two-sided, greater, less |
| `continuity` | `False` | Continuity correction |
| `output` | `cuzick` | Output name |

## 2. 用途与解释

Cuzick's test for an ordered trend across groups.

Rank-based trend test with user-supplied or default group scores.

The statistic is ``T = sum(R_i * l_i)`` over the average rank sum ``R_i``
of each group and its score ``l_i``. Ties are handled with their average
ranks, which gives the same variance as ``PMCMRplus::cuzickTest`` when no
ties are present and a tie-corrected variance otherwise.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension93.py,test_r_oracles89.py |
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
grep '^cuzick,' verification/coverage-8.0.1/operator_coverage.csv
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
