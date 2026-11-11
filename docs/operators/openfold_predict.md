# OpenFold 结构预测 (`openfold_predict`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.openfold_predict:OpenfoldPredictStep`  
**Source:** [`library/seed/src/task/step/steps/openfold_predict.py`](../../library/seed/src/task/step/steps/openfold_predict.py) (223 lines)  
**Trust level: D — 专用测试引用（无真实执行）**

## 1. 代码说明

Run OpenFold (AlphaFold-2 weights) inference for one protein sequence with precomputed single-sequence alignments and return the predicted structure with pLDDT

> openfold_predict: OpenFold (AlphaFold-2) structure

关键符号：

- `def write_fasta() (line 22)`
- `def write_alignment() (line 28)`
- `def openfold_command() (line 38)`
- `def find_prediction() (line 74)`
- `class OpenfoldPredictStep (line 83)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sequence_dim, position_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": false}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sequence_dim` | `sequence` | 序列维度名 |
| `position_dim` | `position` | 位置维度名 |
| `openfold_path` | `` | OpenFold 源码目录 |
| `params_path` | `` | 参数权重 (.pt) |
| `alignment_dir` | `` | 预计算比对目录（可选） |
| `template_dir` | `` | 模板 mmCIF 目录（可选） |
| `config_preset` | `model_1_ptm` | 配置预设; choices: model_1, model_1_ptm, model_2, model_2_ptm, model_3, model_4, model_5 |
| `device` | `cpu` | 设备; choices: cpu, cuda |
| `skip_relaxation` | `True` | 跳过侧链松弛 |
| `python_executable` | `` | Python 解释器 |
| `timeout_seconds` | `3600` | 超时 (秒); min 60; max 14400 |
| `output` | `structure` | 输出参数名 |

## 2. 用途与解释

openfold_predict: OpenFold (AlphaFold-2) structure prediction.

## 3. 正确性依据

**结论：D 级。** 只有专用/冒烟测试引用；没有记录真实执行。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension302.py |
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
grep '^openfold_predict,' verification/coverage-8.0.1/operator_coverage.csv
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
