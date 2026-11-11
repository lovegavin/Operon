# RNA 二级结构距离 (RNAfold 双温度) (`rna_structure_distance`)

**Category:** Sequence  
**Entry point:** `src.task.step.steps.rna_structure_distance:RnaStructureDistanceStep`  
**Source:** [`library/seed/src/task/step/steps/rna_structure_distance.py`](../../library/seed/src/task/step/steps/rna_structure_distance.py) (147 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Fold each RNA with ViennaRNA RNAfold at two temperatures and report the base-pair distance, shared and union pairs, Hamming distance and the normalised base-pair distance between the two

> rna_structure_distance: compare RNA folds at two

关键符号：

- `class RnaStructureDistanceStep (line 20)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sequence_dim, position_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": false}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sequence_dim` | `sequence` | Sequence axis |
| `position_dim` | `position` | Position axis |
| `dangles` | `2` | Dangling ends; choices: 0, 1, 2, 3 |
| `rnafold_path` | `RNAfold` | RNAfold binary |
| `timeout_seconds` | `600` | Timeout (s); min 1 |
| `sequence_output_dim` | `pair` | Output sequence axis |
| `output` | `distances` | Output name |
| `temperature_a` | `37.0` | First temperature (C); min 0.0; max 100.0 |
| `temperature_b` | `50.0` | Second temperature (C); min 0.0; max 100.0 |

## 2. 用途与解释

rna_structure_distance: compare RNA folds at two temperatures.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension399.py |
| L3 真实执行 | ROUTE | operator_table.csv:builtin_route |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | ROUTE | library/seed/routes/rna_structure_compare/task.yaml |

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
grep '^rna_structure_distance,' verification/coverage-8.0.1/operator_coverage.csv
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
