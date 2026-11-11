# Transmembrane helix segments (`sequence_tm_segments`)

**Category:** Sequence  
**Entry point:** `src.task.step.steps.sequence_tm_segments:SequenceTmSegmentsStep`  
**Source:** [`library/seed/src/task/step/steps/sequence_tm_segments.py`](../../library/seed/src/task/step/steps/sequence_tm_segments.py) (252 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Score a protein sequence with Kyte-Doolittle hydropathy windows, merge windows above the membrane threshold into segments and report their ranges and

> Transmembrane helix segments from Kyte-Doolittle hydropathy windows. A residue window is a candidate membrane span when its mean Kyte-Doolittle hydropathy reaches the classic threshold of 1.6. Consecutive candidate windows are merged into segments and short segments are dropped, so the output lists the hydrophobic spans of a sequence together with their

关键符号：

- `def hydropathy_scores() (line 22)`
- `def window_means() (line 34)`
- `def tm_segments() (line 43)`
- `class SequenceTmSegmentsStep (line 87)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sequence_dim, position_dim), info=(alphabet_map, missing_code, representation, unknown_code)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sequence_dim` | `sequence` | 序列维度 |
| `position_dim` | `position` | 位置维度 |
| `window` | `19` | 窗口长度; min 9; max 25 |
| `threshold` | `1.6` | 疏水性阈值; min -5; max 5 |
| `min_length` | `12` | 最短片段长度; min 5; max 50 |
| `output` | `segments` | 输出名称 |

## 2. 用途与解释

Transmembrane helix segments from Kyte-Doolittle hydropathy windows.

A residue window is a candidate membrane span when its mean Kyte-Doolittle
hydropathy reaches the classic threshold of 1.6.  Consecutive candidate windows
are merged into segments and short segments are dropped, so the output lists
the hydrophobic spans of a sequence together with their hydropathy.

Membrane-span candidates from sliding-window hydropathy.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（1.14 s），导出 None 行，产物 sha256 n/a…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension236.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/sequence_tm_segments |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 1.14 s，导出 None 行。
- 归档路线：`/tmp/cov_sequence/sequence_tm_segments`。
- 命令：`/home/gavin/bp-numpy21/bin/python scripts/run.py /tmp/cov_sequence/sequence_tm_segments`。

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
grep '^sequence_tm_segments,' verification/coverage-8.0.1/operator_coverage.csv
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
