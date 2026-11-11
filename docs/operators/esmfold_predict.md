# ESMFold structure prediction (`esmfold_predict`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.esmfold_predict:EsmfoldPredictStep`  
**Source:** [`library/seed/src/task/step/steps/esmfold_predict.py`](../../library/seed/src/task/step/steps/esmfold_predict.py) (186 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Fold one amino-acid sequence with the official ESMFold implementation shipped in fair-esm (esm.pretrained.esmfold_v1) and return the predicted PDB together with its mean pLDDT. The 3B checkpoint is downloaded on first use; set OPERON_ESMFOLD_WEIGHTS or pre-populate the torch hub cache to run

> Structure prediction with the official ESMFold implementation of

关键符号：

- `class EsmfoldPredictStep (line 65)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sequence_dim, position_dim), info=(alphabet_map, representation)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sequence_dim` | `sequence` | 序列维度名; advanced |
| `position_dim` | `position` | 位点维度名; advanced |
| `device` | `cpu` | 运行设备; choices: cpu, cuda |
| `num_recycles` | `4` | 循环次数; min 1; max 48 |
| `chunk_size` | `64` | 分块大小; min 0; max 512; advanced |
| `output` | `structure` | 输出名 |
| `weights_dir` | `` | 本地权重目录 |

## 2. 用途与解释

Structure prediction with the official ESMFold implementation of ``fair-esm``.

Predict one structure with ESMFold and report its confidence.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（55.056 s），导出 1 行，产物 sha256 be565c8e9c4acbc2…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_export_contract.py,test_extension245.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/esmfold_predict |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 55.056 s，导出 1 行。
- 归档路线：`/tmp/esmfold_route`。
- 命令：`run.py /tmp/esmfold_route`。

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
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^esmfold_predict,' verification/coverage-8.0.1/operator_coverage.csv
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
