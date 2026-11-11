# kmer_count (`kmer_count`)

**Category:** analysis  
**Entry point:** `src.task.step.steps.kmer_count:KmerCountStep`  
**Source:** [`library/seed/src/task/step/steps/kmer_count.py`](../../library/seed/src/task/step/steps/kmer_count.py) (186 lines)  
**Trust level: D — 冒烟测试引用（无独立 oracle）**

## 1. 代码说明

Count k-mers per sequence for any sequence-codes

> k-mer counts per sequence for any sequence-codes Form. Input: any Form declaring info["representation"] == "sequence_codes" with info["alphabet"] in {"dna","rna"}. The character-to-code mapping comes from info["alphabet_map"], so the operator works with any reader declaring the same convention. Output: data 2D float32, shape (n_kmers, n_sequences) dims [kmer, sequence] labels kmer = every A/C/G/T word of length k, in lexicographic order sequence = the input's sequence labels Only fully A/C/G/T windows are counted. Windows containing N or any other code are skipped. Different sequence lengths…

关键符号：

- `class KmerCountStep (line 41)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sequence_dim, position_dim), info=(alphabet, alphabet_map, missing_code, representation, unknown_code)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sequence_dim` | `sequence` | — |
| `position_dim` | `position` | — |
| `k` | `3` | min 1; max 6 |
| `output` | `` | — |

## 2. 用途与解释

k-mer counts per sequence for any sequence-codes Form.

Input: any Form declaring info["representation"] == "sequence_codes"
with info["alphabet"] in {"dna","rna"}. The character-to-code mapping
comes from info["alphabet_map"], so the operator works with any reader
declaring the same convention.

Output:
data   2D float32, shape (n_kmers, n_sequences)
dims   [kmer, sequence]
labels kmer = every A/C/G/T word of length k, in lexicographic order
sequence = the input's sequence labels

Only fully A/C/G/T windows are counted. Windows containing N or any
other code are skipped. Different sequence lengths are handled by the
input's NaN padding; windows that would extend past the last defined
position are skipped.

Params:
sequence_dim : name of the sequence axis (default "sequence")
position_dim : name of the position axis (default "position")
k            : word length, 1..6 (default 3)
output

## 3. 正确性依据

**结论：D 级。** 只有专用/冒烟测试引用；没有记录真实执行。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | SMOKE | operator_table.csv:contract_positive |
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
grep '^kmer_count,' verification/coverage-8.0.1/operator_coverage.csv
```

算子手册中的示例：

```text
Use the registry to discover compatible Readers and validate a complete workflow
before execution. This generated page does not claim an executable scientific
example. Add a tested example and replace this generated page with authored
guidance when extending this operator.
```

未补齐证据：`L2_ORACLE,L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
