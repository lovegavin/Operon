# ColabFold structure prediction (`colabfold_predict`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.colabfold_predict:ColabfoldPredictStep`  
**Source:** [`library/seed/src/task/step/steps/colabfold_predict.py`](../../library/seed/src/task/step/steps/colabfold_predict.py) (282 lines)  
**Trust level: D — 专用测试引用（无真实执行）**

## 1. 代码说明

Predict a protein structure from one amino-acid sequence with the official colabfold_batch runner and return the rank-001 PDB together with the mean pLDDT, pTM and maximum PAE recorded in the ColabFold scores

> Structure prediction with the official ColabFold ``colabfold_batch``

关键符号：

- `def write_fasta() (line 25)`
- `def rank_pdb() (line 33)`
- `def parse_scores() (line 43)`
- `def predict() (line 62)`
- `class ColabfoldPredictStep (line 130)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sequence_dim, position_dim), info=(alphabet_map, representation)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sequence_dim` | `sequence` | 序列维度名; advanced |
| `position_dim` | `position` | 位点维度名; advanced |
| `colabfold_path` | `colabfold_batch` | colabfold_batch 路径（默认取 PATH） |
| `num_models` | `1` | 模型数; min 1; max 5 |
| `num_recycles` | `3` | 循环次数; min 1; max 48 |
| `msa_mode` | `mmseqs2_uniref_env` | MSA 模式; choices: mmseqs2_uniref_env, mmseqs2_uniref, single_sequence; advanced |
| `device` | `cpu` | 运行设备; choices: cpu, cuda; advanced |
| `timeout_seconds` | `3600` | 超时（秒）; min 60; max 86400; advanced |
| `output` | `structure` | 输出名 |

## 2. 用途与解释

Structure prediction with the official ColabFold ``colabfold_batch`` runner.

Predict one structure with the official ColabFold batch runner.

## 3. 正确性依据

**结论：D 级。** 只有专用/冒烟测试引用；没有记录真实执行。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension244.py,test_extension357.py |
| L3 真实执行 | SKIP | no route in audit, archive, or srv evidence |
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
grep '^colabfold_predict,' verification/coverage-8.0.1/operator_coverage.csv
```

算子手册中的示例：

```text
Use the registry to discover compatible Readers and validate a complete workflow
before execution. This generated page does not claim an executable scientific
example. Add a tested example and replace this generated page with authored
guidance when extending this operator.
```

未补齐证据：`L3,L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
