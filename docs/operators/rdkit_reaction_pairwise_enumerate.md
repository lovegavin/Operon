# Pairwise reaction enumeration (`rdkit_reaction_pairwise_enumerate`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.rdkit_reaction_pairwise_enumerate:RdkitReactionPairwiseEnumerateStep`  
**Source:** [`library/seed/src/task/step/steps/rdkit_reaction_pairwise_enumerate.py`](../../library/seed/src/task/step/steps/rdkit_reaction_pairwise_enumerate.py) (219 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Apply a two-component reaction SMARTS to the cross product of two SMILES libraries, deduplicate the products and report heavy-atom count and molecular weight per

> Pairwise reaction enumeration over two reactant libraries. ``rdkit_reaction_smarts_apply`` applies a one-component reaction to each molecule. Amide couplings, Suzuki couplings and reductive aminations need two reactants, so this operator enumerates the cross product of two SMILES libraries, deduplicates the products and records their

关键符号：

- `def reaction_from_smarts() (line 22)`
- `def enumerate_pairs() (line 46)`
- `class RdkitReactionPairwiseEnumerateStep (line 98)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `reactants_a` | `` | 反应物 A 库 |
| `reactants_b` | `` | 反应物 B 库 |
| `reaction_smarts` | `` | 反应 SMARTS |
| `max_products` | `100` | 产物上限; min 1; max 5000 |
| `max_products_per_pair` | `20` | 单对上限; min 1; max 200 |
| `dedupe` | `True` | 产物去重 |
| `output` | `products` | 输出槽 |

## 2. 用途与解释

Pairwise reaction enumeration over two reactant libraries.

``rdkit_reaction_smarts_apply`` applies a one-component reaction to each
molecule.  Amide couplings, Suzuki couplings and reductive aminations need two
reactants, so this operator enumerates the cross product of two SMILES
libraries, deduplicates the products and records their size.

Enumerate two-component reaction products across two libraries.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（0.7 s），导出 None 行，产物 sha256 79c96e9c8dd22c58…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension275.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/rdkit_reaction_pairwise_enumerate |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 0.7 s，导出 None 行。
- 归档路线：`/tmp/cov_mltab/rdkit_reaction_pairwise_enumerate`。
- 命令：`cd /path/to/Operon-worktree && python scripts/run.py /tmp/cov_mltab/rdkit_reaction_pairwise_enumerate`。

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
grep '^rdkit_reaction_pairwise_enumerate,' verification/coverage-8.0.1/operator_coverage.csv
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
