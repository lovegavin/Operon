# Standardize SMILES (`smiles_standardize`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.smiles_standardize:SmilesStandardizeStep`  
**Source:** [`library/seed/src/task/step/steps/smiles_standardize.py`](../../library/seed/src/task/step/steps/smiles_standardize.py) (168 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Optionally keep the largest fragment, neutralize charges and write canonical RDKit SMILES for every input molecule. The output is a [molecule, statistic] Form with atom, heavy-atom, fragment and ring counts; the canonical strings are exposed in

> Standardize SMILES strings and report their molecular

关键符号：

- `class SmilesStandardizeStep (line 22)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `smiles` | `` | SMILES 列表 |
| `keep_largest_fragment` | `True` | 保留最大片段 |
| `neutralize` | `False` | 中和电荷; advanced |
| `molecule_dim` | `molecule` | 分子维度; advanced |
| `output` | `standardized` | 输出名; advanced |

## 2. 用途与解释

Standardize SMILES strings and report their molecular composition.

Canonicalize SMILES strings and report basic composition statistics.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（0.9 s），导出 None 行，产物 sha256 a7e48ab2db139521…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension114.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/smiles_standardize |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 0.9 s，导出 None 行。
- 归档路线：`/tmp/cov_mltab/smiles_standardize`。
- 命令：`cd /path/to/Operon-worktree && python scripts/run.py /tmp/cov_mltab/smiles_standardize`。

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
grep '^smiles_standardize,' verification/coverage-8.0.1/operator_coverage.csv
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
