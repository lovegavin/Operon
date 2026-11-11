# Sequence Complexity (`sequence_complexity`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.sequence_complexity:SequenceComplexityStep`  
**Source:** [`library/seed/src/task/step/steps/sequence_complexity.py`](../../library/seed/src/task/step/steps/sequence_complexity.py) (204 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Measure protein sequence complexity with k-mer Shannon entropy, linguistic complexity and the fraction of low-complexity windows, useful for filtering repeat-rich or low-entropy designed

> Sequence complexity metrics for low-complexity and repeat

关键符号：

- `def shannon_entropy() (line 28)`
- `def linguistic_complexity() (line 39)`
- `def low_complexity_fraction() (line 53)`
- `def complexity_row() (line 68)`
- `class SequenceComplexityStep (line 83)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sequence_dim, position_dim), info=(alphabet, missing_code, representation)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sequence_dim` | `sequence` | 序列维度 |
| `position_dim` | `position` | 位置维度 |
| `window` | `20` | 低复杂度窗口; min 5; max 200; advanced |
| `low_complexity_entropy` | `2.0` | 低复杂度阈值 (bits); min 0.0; max 4.32; advanced |
| `output` | `output` | 输出名称 |

## 2. 用途与解释

Sequence complexity metrics for low-complexity and repeat detection.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension152.py,test_extension153.py |
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
grep '^sequence_complexity,' verification/coverage-8.0.1/operator_coverage.csv
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
