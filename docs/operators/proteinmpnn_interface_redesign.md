# Interface Redesign (`proteinmpnn_interface_redesign`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.proteinmpnn_interface_redesign:ProteinmpnnInterfaceRedesignStep`  
**Source:** [`library/seed/src/task/step/steps/proteinmpnn_interface_redesign.py`](../../library/seed/src/task/step/steps/proteinmpnn_interface_redesign.py) (343 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Design only binder residues at the target interface with

> Design only the binder residues that contact a target

关键符号：

- `def protein_residues() (line 72)`
- `def split_chains() (line 91)`
- `def interface_residues() (line 95)`
- `def fixed_payload() (line 118)`
- `class ProteinmpnnInterfaceRedesignStep (line 134)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `structure_path` | `` | 结构文件路径 |
| `proteinmpnn_path` | `` | ProteinMPNN 目录 |
| `binder_chains` | `A` | Binder 链 |
| `target_chains` | `` | Target 链 |
| `cutoff` | `8.0` | 界面截断距离 (A); min 1.0; max 20.0 |
| `num_seq_per_target` | `4` | 每条序列数; min 1; max 500 |
| `sampling_temp` | `0.1` | 采样温度; advanced |
| `seed` | `1` | 随机种子; min 0; advanced |
| `model_name` | `v_48_020` | 模型; choices: v_48_002, v_48_010, v_48_020, v_48_030; advanced |
| `weights_path` | `` | 权重目录; advanced |
| `device` | `cpu` | 设备; choices: cpu, cuda; advanced |
| `timeout` | `3600` | 超时 (秒); min 10; advanced |
| `python_executable` | `` | Python 解释器; advanced |
| `output` | `designs` | 输出名; advanced |

## 2. 用途与解释

Design only the binder residues that contact a target chain.

Redesign the binder interface with the official ProteinMPNN runner.

## 3. 正确性依据

**结论：B 级。** 服务器真实运行通过（9.0075 s），1 个步骤产物，首个 sha256 350b92cd63d08667…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension183.py,test_extension359.py |
| L3 真实执行 | EXECUTED_SRV | srv:/public/home/lihj/operon715/cov_mpnn2/proteinmpnn_interface_redesign/output/run_summary.json |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

服务器执行细节：

- 状态：complete，总耗时 9.0075 s，步骤 1。
- 路线：`/path/to/server-worktree/operon715/cov_mpnn2/proteinmpnn_interface_redesign`；run_id `20261110T143553-5df8a2c5d332`。

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
grep '^proteinmpnn_interface_redesign,' verification/coverage-8.0.1/operator_coverage.csv
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
