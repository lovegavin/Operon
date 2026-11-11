# CpG island scan (`sequence_cpg_island`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.sequence_cpg_island:SequenceCpgIslandStep`  
**Source:** [`library/seed/src/task/step/steps/sequence_cpg_island.py`](../../library/seed/src/task/step/steps/sequence_cpg_island.py) (188 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Sliding-window CpG island detection using GC content and observed/expected CpG ratio, with merged island

> CpG island scan with GC content and observed/expected CpG

关键符号：

- `def island_windows() (line 13)`
- `def merge_windows() (line 38)`
- `class SequenceCpgIslandStep (line 57)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sequence_dim, position_dim), info=(representation)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sequence_dim` | `sequence` | 序列维度 |
| `position_dim` | `position` | 位置维度 |
| `island_dim` | `island` | 岛屿维度; advanced |
| `window` | `200` | 窗口长度; min 20; max 5000 |
| `step` | `10` | 窗口步长; min 1 |
| `gc_min` | `0.5` | 最小 GC 含量; min 0.01; max 1.0 |
| `cpg_oe_min` | `0.6` | 最小 CpG 观测/期望比; min 0.0 |
| `output` | `islands` | 输出名; advanced |

## 2. 用途与解释

CpG island scan with GC content and observed/expected CpG criteria.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension215.py |
| L3 真实执行 | ROUTE | operator_table.csv:generated_route |
| L4 资源 | SKIP | no memory estimate |
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
grep '^sequence_cpg_island,' verification/coverage-8.0.1/operator_coverage.csv
```

算子手册中的示例：

```text
Use the registry to discover compatible Readers and validate a complete workflow
before execution. This generated page does not claim an executable scientific
example. Add a tested example and replace this generated page with authored
guidance when extending this operator.
```

未补齐证据：`L4`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
