# ProteinMPNN position entropy (`proteinmpnn_position_entropy`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.proteinmpnn_position_entropy:ProteinmpnnPositionEntropyStep`  
**Source:** [`library/seed/src/task/step/steps/proteinmpnn_position_entropy.py`](../../library/seed/src/task/step/steps/proteinmpnn_position_entropy.py) (321 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Sample ProteinMPNN designs for a structure and summarise the per-position amino-acid entropy and native

> Per-position amino-acid entropy from ProteinMPNN sampled

关键符号：

- `def read_fasta() (line 22)`
- `def split_designs() (line 40)`
- `def position_entropy() (line 59)`
- `def designer_command() (line 98)`
- `def run_designer() (line 130)`
- `class ProteinmpnnPositionEntropyStep (line 163)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info": {"missing_code": {"type": ["number", "null"]}}, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `structure_path` | `` | 结构文件 |
| `proteinmpnn_path` | `` | ProteinMPNN 仓库路径 |
| `weights_path` | `` | 权重目录; advanced |
| `python_executable` | `` | Python 解释器; advanced |
| `model_name` | `v_48_020` | 模型; choices: v_48_002, v_48_010, v_48_020, v_48_030 |
| `num_seq_per_target` | `8` | 采样序列数; min 2; max 500 |
| `sampling_temp` | `0.1` | 采样温度 |
| `seed` | `1` | 随机种子; min 0; advanced |
| `chains` | `` | 设计链; advanced |
| `device` | `cpu` | 设备; choices: cpu, cuda; advanced |
| `timeout` | `1800` | 超时（秒）; min 1; max 86400; advanced |
| `output` | `entropy` | 输出; advanced |

## 2. 用途与解释

Per-position amino-acid entropy from ProteinMPNN sampled designs.

## 3. 正确性依据

**结论：B 级。** 服务器真实运行通过（132.8268 s），1 个步骤产物，首个 sha256 7b7c6250bbda6927…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension164.py,test_extension169.py,test_extension170.py |
| L3 真实执行 | EXECUTED_SRV | srv:/public/home/lihj/operon715/closure_replay/proteinmpnn_position_entropy/output/run_summary.json |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

服务器执行细节：

- 状态：complete，总耗时 132.8268 s，步骤 1。
- 路线：`/path/to/server-worktree/operon715/closure_replay/proteinmpnn_position_entropy`；run_id `20261110T125100-7cc2d39464cd`。

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
grep '^proteinmpnn_position_entropy,' verification/coverage-8.0.1/operator_coverage.csv
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
