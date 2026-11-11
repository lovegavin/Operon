# find_orfs (`find_orfs`)

**Category:** analysis  
**Entry point:** `src.task.step.steps.find_orfs:FindOrfsStep`  
**Source:** [`library/seed/src/task/step/steps/find_orfs.py`](../../library/seed/src/task/step/steps/find_orfs.py) (235 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Locate complete ATG..stop ORFs on both

> Find complete ORFs (ATG..stop) in any sequence-codes Form. Input: any Form declaring info["representation"] == "sequence_codes" with info["alphabet"] in {"dna","rna"}. Output: data 2D float32, shape (n_orfs, 6) dims [orf, statistic] statistic = [strand, frame, start, end, length_nt, length_aa] info["sequence"] is axis-parallel to "orf", naming each ORF's source sequence label. Both strands are scanned. Forward strand uses strand=+1; the reverse complement uses strand=-1. For each chain, frames 0,1,2 start the codon grid at that offset. From every ATG, the first in-frame stop (TAA/TAG/TGA)…

关键符号：

- `class FindOrfsStep (line 57)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sequence_dim, position_dim), info=(alphabet, alphabet_map, missing_code, representation, unknown_code)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sequence_dim` | `sequence` | — |
| `position_dim` | `position` | — |
| `min_aa` | `1` | min 1 |
| `output` | `` | — |

## 2. 用途与解释

Find complete ORFs (ATG..stop) in any sequence-codes Form.

Input: any Form declaring info["representation"] == "sequence_codes"
with info["alphabet"] in {"dna","rna"}.

Output:
data   2D float32, shape (n_orfs, 6)
dims   [orf, statistic]
statistic = [strand, frame, start, end, length_nt, length_aa]
info["sequence"] is axis-parallel to "orf", naming each ORF's
source sequence label.

Both strands are scanned. Forward strand uses strand=+1; the reverse
complement uses strand=-1. For each chain, frames 0,1,2 start the
codon grid at that offset. From every ATG, the first in-frame stop
(TAA/TAG/TGA) closes an ORF. start and end are 0-based positions on
the chain that strand refers to; end is the last base of the stop
codon, so length_nt == end - start + 1 and length_aa == length_nt/3 - 1.

Params:
sequence_dim : name of the sequence axis (default "sequence")
position_dim : name of the positi

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension202.py |
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
grep '^find_orfs,' verification/coverage-8.0.1/operator_coverage.csv
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
