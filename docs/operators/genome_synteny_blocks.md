# Genome synteny blocks (`genome_synteny_blocks`)

**Category:** Genome  
**Entry point:** `src.task.step.steps.genome_synteny_blocks:GenomeSyntenyBlocksStep`  
**Source:** [`library/seed/src/task/step/steps/genome_synteny_blocks.py`](../../library/seed/src/task/step/steps/genome_synteny_blocks.py) (150 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Chain minimap2 alignments into collinear synteny blocks between two

> Collinear synteny blocks between two

关键符号：

- `class GenomeSyntenyBlocksStep (line 28)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=?, numeric=?, dims=(—), info=(—)
- 输入 2: ndim=?, numeric=?, dims=(—), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "dims": [{"param": "block_dim", "default": "block"}, {"param": "field_dim", "default": "field"}]}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `preset` | `asm5` | minimap2 alignment preset for closely related; choices: asm5, asm10, asm20 |
| `min_block` | `1000` | Minimum alignment or block length in base; min 100 |
| `min_identity` | `0.0` | Minimum per-alignment identity to; min 0.0; max 1.0 |
| `max_reference_gap` | `50000` | Largest unaligned reference gap bridged inside one synteny; min 0 |
| `threads` | `1` | min 1 |
| `timeout_seconds` | `1800` | min 1 |
| `minimap2_path` | `minimap2` | — |
| `query_sequence_dim` | `sequence` | — |
| `query_position_dim` | `position` | — |
| `reference_sequence_dim` | `sequence` | — |
| `reference_position_dim` | `position` | — |
| `output` | `blocks` | — |
| `block_dim` | `block` | — |
| `field_dim` | `field` | — |

## 2. 用途与解释

Collinear synteny blocks between two assemblies.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension400.py |
| L3 真实执行 | ROUTE | operator_table.csv:builtin_route |
| L4 资源 | MEASURED | operator_table.csv:deterministic |
| L5 应用安装 | ROUTE | library/seed/routes/genome_comparison/task.yaml |

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
grep '^genome_synteny_blocks,' verification/coverage-8.0.1/operator_coverage.csv
```

算子手册中的示例：

```text
Use the registry to discover compatible Readers and validate a complete workflow
before execution. This generated page does not claim an executable scientific
example. Add a tested example and replace this generated page with authored
guidance when extending this operator.
```

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
