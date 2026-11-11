# RDKit fragment overlap (`rdkit_fragment_overlap`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.rdkit_fragment_overlap:RdkitFragmentOverlapStep`  
**Source:** [`library/seed/src/task/step/steps/rdkit_fragment_overlap.py`](../../library/seed/src/task/step/steps/rdkit_fragment_overlap.py) (169 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Compare two molecule groups through their BRICS fragment sets: the output is the Jaccard overlap (shared / union) of every molecule of the first group against every molecule of the second group. Groups are given as 'SMILES [name]'

> BRICS fragment overlap between two molecule

关键符号：

- `def clean_fragment() (line 13)`
- `def brics_fragments() (line 19)`
- `def fragment_sets() (line 36)`
- `def overlap_matrix() (line 43)`
- `class RdkitFragmentOverlapStep (line 54)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `smiles_a` | `` | 分子组 A |
| `smiles_b` | `` | 分子组 B |
| `min_fragment_size` | `4` | 最小片段重原子数; min 1 |
| `molecule_a_dim` | `molecule_a` | 组 A 分子维度; advanced |
| `molecule_b_dim` | `molecule_b` | 组 B 分子维度; advanced |
| `output` | `fragment_overlap` | 输出名称; advanced |

## 2. 用途与解释

BRICS fragment overlap between two molecule groups.

Jaccard overlap of BRICS fragment sets between two molecule groups.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（0.67 s），导出 None 行，产物 sha256 4fb7dff37af1ba37…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension189.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/rdkit_fragment_overlap |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 0.67 s，导出 None 行。
- 归档路线：`/tmp/cov_mltab/rdkit_fragment_overlap`。
- 命令：`cd /path/to/Operon-worktree && python scripts/run.py /tmp/cov_mltab/rdkit_fragment_overlap`。

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
grep '^rdkit_fragment_overlap,' verification/coverage-8.0.1/operator_coverage.csv
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
