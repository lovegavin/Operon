# RNA 可及性 (`sequence_rna_accessibility`)

**Category:** Sequence  
**Entry point:** `src.task.step.steps.sequence_rna_accessibility:SequenceRnaAccessibilityStep`  
**Source:** [`library/seed/src/task/step/steps/sequence_rna_accessibility.py`](../../library/seed/src/task/step/steps/sequence_rna_accessibility.py) (152 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Compute the Boltzmann ensemble base-pair probabilities with ViennaRNA and report per-base unpaired probabilities plus accessible single-stranded

> sequence_rna_accessibility: per-base unpaired probabilities from the

关键符号：

- `def pairing_probabilities() (line 26)`
- `def accessibility_rows() (line 50)`
- `class SequenceRnaAccessibilityStep (line 76)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sequence_dim, position_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": false}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sequence_dim` | `sequence` | 序列维度名 |
| `position_dim` | `position` | 位置维度名 |
| `temperature` | `37.0` | 温度（°C）; min 1.0; max 99.0 |
| `threshold` | `0.5` | 可及阈值; min 0.0; max 1.0 |
| `min_length` | `2` | 最短可及片段; min 1; max 50 |
| `output` | `accessibility` | 输出参数名 |

## 2. 用途与解释

sequence_rna_accessibility: per-base unpaired probabilities from the ensemble.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（1.23 s），导出 None 行，产物 sha256 n/a…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension336.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/sequence_rna_accessibility |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 1.23 s，导出 None 行。
- 归档路线：`/tmp/cov_sequence/sequence_rna_accessibility`。
- 命令：`python scripts/run.py /tmp/cov_sequence/sequence_rna_accessibility`。

服务器执行细节：

- 状态：complete，总耗时 0.3461 s，步骤 1。
- 路线：`/path/to/server-worktree/operon715/closure_replay/sequence_rna_accessibility`；run_id `20261110T123417-e4aeb231b80e`。

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
grep '^sequence_rna_accessibility,' verification/coverage-8.0.1/operator_coverage.csv
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
