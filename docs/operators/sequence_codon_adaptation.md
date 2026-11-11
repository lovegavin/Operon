# Codon adaptation index (`sequence_codon_adaptation`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.sequence_codon_adaptation:SequenceCodonAdaptationStep`  
**Source:** [`library/seed/src/task/step/steps/sequence_codon_adaptation.py`](../../library/seed/src/task/step/steps/sequence_codon_adaptation.py) (258 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Codon adaptation index of coding DNA sequences relative to a reference coding set (Sharp & Li

> Codon adaptation index (CAI) of coding sequences. The CAI (Sharp & Li, 1987) is the geometric mean of the relative adaptiveness ``w`` of every codon in a target coding sequence, where ``w`` comes from the codon counts of a reference coding set. The definition follows Biopython's ``Bio.SeqUtils.CodonAdaptationIndex``: codons absent from the reference get the paper's 0.5 pseudo-count, ATG and TGG are excluded from the mean, and stop codons are included only when the reference defines

关键符号：

- `def codon_weights() (line 58)`
- `def adaptation_index() (line 84)`
- `class SequenceCodonAdaptationStep (line 119)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sequence_dim, position_dim), info=(representation)
- 输入 2: ndim=2, numeric=True, dims=(reference_sequence_dim, reference_position_dim), info=(representation)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sequence_dim` | `sequence` | 序列维度 |
| `position_dim` | `position` | 位置维度 |
| `reference_sequence_dim` | `sequence` | 参考序列维度; advanced |
| `reference_position_dim` | `position` | 参考位置维度; advanced |
| `sequence_output_dim` | `sequence` | 输出序列维度; advanced |
| `absent_weight` | `0.5` | 缺失密码子权重; min 1e-06; max 1.0; advanced |
| `exclude_singletons` | `True` | 排除 ATG/TGG; advanced |
| `output` | `cai` | 输出名称; advanced |

## 2. 用途与解释

Codon adaptation index (CAI) of coding sequences.

The CAI (Sharp & Li, 1987) is the geometric mean of the relative adaptiveness
``w`` of every codon in a target coding sequence, where ``w`` comes from the
codon counts of a reference coding set.  The definition follows Biopython's
``Bio.SeqUtils.CodonAdaptationIndex``: codons absent from the reference get the
paper's 0.5 pseudo-count, ATG and TGG are excluded from the mean, and stop
codons are included only when the reference defines them.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension229.py |
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
grep '^sequence_codon_adaptation,' verification/coverage-8.0.1/operator_coverage.csv
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
