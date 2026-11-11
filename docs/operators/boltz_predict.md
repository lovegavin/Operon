# Boltz co-folding prediction (`boltz_predict`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.boltz_predict:BoltzPredictStep`  
**Source:** [`library/seed/src/task/step/steps/boltz_predict.py`](../../library/seed/src/task/step/steps/boltz_predict.py) (226 lines)
**Trust level: D — 专用测试引用（无真实执行）**

## 1. 代码说明

(descriptor has no description)

> Boltz-2 co-folding prediction

关键符号：

- `def write_yaml() (line 24)`
- `def boltz_command() (line 42)`
- `def find_outputs() (line 88)`
- `def parse_confidence() (line 101)`
- `def parse_affinity() (line 118)`
- `class BoltzPredictStep (line 128)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sequence_dim, position_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": false}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sequence_dim` | `sequence` | 序列维 |
| `position_dim` | `position` | 位置维 |
| `protein_chain` | `A` | 蛋白链 |
| `ligand_smiles` | `` | 配体 SMILES |
| `ligand_chain` | `B` | 配体链 |
| `affinity` | `False` | 预测亲和力 |
| `model` | `boltz2` | 模型; choices: boltz2, boltz1 |
| `use_msa_server` | `True` | MSA 服务器 |
| `device` | `cpu` | 设备; choices: cpu, cuda |
| `extra_args` | `` | 额外参数 |
| `boltz_path` | `boltz` | boltz 命令 |
| `timeout_seconds` | `3600` | 超时 (s); min 60; max 21600 |
| `output` | `structure` | 输出 |
| `output_format` | `pdb` | 输出格式; choices: pdb, mmcif |
| `sampling_steps` | `200` | 采样步数; min 1; max 1000 |
| `diffusion_samples` | `1` | 扩散样本数; min 1; max 32 |
| `num_workers` | `1` | 数据线程; min 0; max 16 |
| `no_kernels` | `False` | 禁用 kernel |
| `msa_mode` | `server` | MSA 模式; choices: server, empty |
| `cache_dir` | `` | 权重缓存目录 |

## 2. 用途与解释

Boltz-2 co-folding prediction wrapper.

## 3. 正确性依据

**结论：D 级。** 只有专用/冒烟测试引用；没有记录真实执行。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_export_contract.py,test_extension292.py,test_remote_provision.py |
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
cd /path/to/Operon-worktree
python -m operon registry check --json
grep '^boltz_predict,' verification/coverage-8.0.1/operator_coverage.csv
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
