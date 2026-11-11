# ProteinMPNN noise robustness (`proteinmpnn_noise_robustness`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.proteinmpnn_noise_robustness:ProteinmpnnNoiseRobustnessStep`  
**Source:** [`library/seed/src/task/step/steps/proteinmpnn_noise_robustness.py`](../../library/seed/src/task/step/steps/proteinmpnn_noise_robustness.py) (399 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Perturb the backbone coordinates with increasing Gaussian noise, redesign every replicate with the official ProteinMPNN runner and report the mean sequence recovery and model scores per noise level as a measure of design

> ProteinMPNN design robustness across backbone coordinate noise levels. Each replicate perturbs the atom coordinates with zero-mean Gaussian noise and redesigns the structure with the official ProteinMPNN runner, so the reported sequence recovery and model scores describe how sensitive a design task is to small backbone displacements rather than to sampling

关键符号：

- `def parse_levels() (line 38)`
- `def pdb_coordinates() (line 73)`
- `def perturb_coordinates() (line 91)`
- `def write_perturbed() (line 101)`
- `def noise_row() (line 119)`
- `def run_replicate() (line 136)`
- `class ProteinmpnnNoiseRobustnessStep (line 228)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `structure_path` | `` | 结构文件路径 |
| `chains` | `` | 设计链 |
| `noise_levels` | `0,1,2` | 噪声水平 |
| `replicates` | `1` | 重复次数; min 1; max 5 |
| `num_seq_per_target` | `8` | 每条链序列数; min 1 |
| `sampling_temp` | `0.1` | 采样温度 |
| `seed` | `0` | 随机种子 |
| `model_name` | `v_48_020` | 模型; choices: v_48_002, v_48_010, v_48_020, v_48_030 |
| `proteinmpnn_path` | `` | ProteinMPNN 路径 |
| `weights_path` | `` | 权重目录 |
| `python_executable` | `` | Python 可执行文件 |
| `device` | `cpu` | 设备; choices: cpu, cuda |
| `timeout_seconds` | `1800` | 超时时间; min 1 |
| `output` | `noise` | 输出名称 |

## 2. 用途与解释

ProteinMPNN design robustness across backbone coordinate noise levels.

Each replicate perturbs the atom coordinates with zero-mean Gaussian noise and
redesigns the structure with the official ProteinMPNN runner, so the reported
sequence recovery and model scores describe how sensitive a design task is to
small backbone displacements rather than to sampling randomness.

ProteinMPNN sequence recovery under increasing backbone noise.

## 3. 正确性依据

**结论：B 级。** 服务器真实运行通过（527.5713 s），1 个步骤产物，首个 sha256 85949db57de0dd0b…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension233.py |
| L3 真实执行 | EXECUTED_SRV | srv:/public/home/lihj/operon715/cov_mpnn/proteinmpnn_noise_robustness/output/run_summary.json |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

服务器执行细节：

- 状态：complete，总耗时 527.5713 s，步骤 1。
- 路线：`/public/home/lihj/operon715/cov_mpnn/proteinmpnn_noise_robustness`；run_id `20261110T141240-e5b8717eb75a`。

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
grep '^proteinmpnn_noise_robustness,' verification/coverage-8.0.1/operator_coverage.csv
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
