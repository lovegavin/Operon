# gc_skew_profile (`gc_skew_profile`)

**Category:** Omics  
**Entry point:** `src.task.step.steps.gc_skew_profile:GcSkewProfileStep`  
**Source:** [`library/seed/src/task/step/steps/gc_skew_profile.py`](../../library/seed/src/task/step/steps/gc_skew_profile.py) (281 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

GC / AT composition and cumulative GC skew over sliding

> Sliding-window GC and AT composition with cumulative GC skew. Input: any Form declaring info["representation"] == "sequence_codes" with info["alphabet"] in {"dna", "rna"}. The alphabet_map identifies which numeric code stands for each of A, C, G, T; U is treated as T. The input must contain exactly one sequence on the sequence axis. Use select on the sequence axis first if the source has several. For every window of window_size positions (default 10000), starting at multiples of step_size (default = window_size): gc (G + C) / valid at (A + T) / valid gc_skew (G - C) / (G + C) NaN when G + C…

关键符号：

- `class GcSkewProfileStep (line 56)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sequence_dim, position_dim), info=(alphabet, alphabet_map, missing_code, representation, unknown_code)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sequence_dim` | `sequence` | 序列维度 |
| `position_dim` | `position` | 位置维度 |
| `window_size` | `10000` | 窗口大小; min 1 |
| `step_size` | `None` | 步长 |
| `output` | `` | 输出名称 |

## 2. 用途与解释

Sliding-window GC and AT composition with cumulative GC skew.

Input: any Form declaring info["representation"] == "sequence_codes"
with info["alphabet"] in {"dna", "rna"}. The alphabet_map identifies
which numeric code stands for each of A, C, G, T; U is treated as T.

The input must contain exactly one sequence on the sequence axis.
Use select on the sequence axis first if the source has several.

For every window of window_size positions (default 10000), starting
at multiples of step_size (default = window_size):

gc        (G + C) / valid
at        (A + T) / valid
gc_skew   (G - C) / (G + C)         NaN when G + C is zero
cumulative_skew
running (sum of G - C) / (running sum of G + C)
accumulated across every window emitted so far, NaN
when the running (G + C) is zero.
cumulative_gc
running sum of (G - C) across emitted windows.

valid counts A, C, G, T; N and other codes are exclude

## 3. 正确性依据

**结论：B 级。** 真实运行通过（1.54 s），导出 None 行，产物 sha256 cee1455c58c7cb07…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_l2_gap.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/gc_skew_profile |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 1.54 s，导出 None 行。
- 归档路线：`/tmp/cov_omics/gc_skew_profile`。
- 命令：`python scripts/run.py /tmp/cov_omics/gc_skew_profile`。

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
grep '^gc_skew_profile,' verification/coverage-8.0.1/operator_coverage.csv
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
