# Boltz-2 亲和力预测汇总 (`boltz_affinity_summary`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.boltz_affinity_summary:BoltzAffinitySummaryStep`  
**Source:** [`library/seed/src/task/step/steps/boltz_affinity_summary.py`](../../library/seed/src/task/step/steps/boltz_affinity_summary.py) (141 lines)
**Trust level: D — 专用测试引用（无真实执行）**

## 1. 代码说明

Read Boltz-2 affinity_*.json files and tabulate the predicted binding affinity value and binder probability, with the best prediction in

> boltz_affinity_summary: parse Boltz-2 affinity

关键符号：

- `def parse_affinity() (line 18)`
- `def collect_affinity() (line 44)`
- `def affinity_rows() (line 55)`
- `def best_summary() (line 69)`
- `class BoltzAffinitySummaryStep (line 81)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": false}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `affinity_path` | `` | 亲和力 JSON 或输出目录 |
| `model_dim` | `complex` | 预测维度名 |
| `output` | `affinity` | 输出参数名 |

## 2. 用途与解释

boltz_affinity_summary: parse Boltz-2 affinity predictions.

## 3. 正确性依据

**结论：D 级。** 只有专用/冒烟测试引用；没有记录真实执行。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension301.py |
| L3 真实执行 | SKIP | no route in audit, archive, or srv evidence |
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
grep '^boltz_affinity_summary,' verification/coverage-8.0.1/operator_coverage.csv
```

算子手册中的示例：

```text
Use the registry to discover compatible Readers and validate a complete workflow
before execution. This generated page does not claim an executable scientific
example. Add a tested example and replace this generated page with authored
guidance when extending this operator.
```

未补齐证据：`L3,L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
