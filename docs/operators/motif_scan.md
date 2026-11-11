# motif_scan (`motif_scan`)

**Category:** analysis  
**Entry point:** `src.task.step.steps.motif_scan:MotifScanStep`  
**Source:** [`library/seed/src/task/step/steps/motif_scan.py`](../../library/seed/src/task/step/steps/motif_scan.py) (213 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Count IUPAC motif occurrences per

> Scan IUPAC motifs across any sequence-codes Form. Input: any Form declaring info["representation"] == "sequence_codes" with info["alphabet"] in {"dna","rna"}. Motifs come in as {"name": "IUPAC-pattern"} and are matched on the forward strand. Each window of the same length is compared using the IUPAC convention: A C G T U -> single base R = A|G Y = C|T S = G|C W = A|T K = G|T M = A|C B = C|G|T D = A|G|T H = A|C|T V = A|C|G N = any Output: data 2D float32, shape (n_motifs, n_sequences) dims [motif, sequence] labels motif = user-supplied names, in insertion order sequence = input sequence labels…

关键符号：

- `class MotifScanStep (line 47)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sequence_dim, position_dim), info=(alphabet, alphabet_map, missing_code, representation, unknown_code)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sequence_dim` | `sequence` | — |
| `position_dim` | `position` | — |
| `motifs` | `` | — |
| `output` | `` | — |

## 2. 用途与解释

Scan IUPAC motifs across any sequence-codes Form.

Input: any Form declaring info["representation"] == "sequence_codes"
with info["alphabet"] in {"dna","rna"}.

Motifs come in as {"name": "IUPAC-pattern"} and are matched on the
forward strand. Each window of the same length is compared using the
IUPAC convention:

A C G T U -> single base
R = A|G    Y = C|T    S = G|C    W = A|T
K = G|T    M = A|C    B = C|G|T  D = A|G|T
H = A|C|T  V = A|C|G  N = any

Output:
data   2D float32, shape (n_motifs, n_sequences)
dims   [motif, sequence]
labels motif = user-supplied names, in insertion order
sequence = input sequence labels

Counts include overlapping occurrences. Windows crossing N, unknown
codes or the NaN padding are skipped.

Params:
sequence_dim : name of the sequence axis (default "sequence")
position_dim : name of the position axis (default "position")
motifs       : {"name": "IUPAC-str

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_l2_gap.py |
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
cd /path/to/Operon-worktree
python -m operon registry check --json
grep '^motif_scan,' verification/coverage-8.0.1/operator_coverage.csv
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
