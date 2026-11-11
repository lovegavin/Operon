# ProteinMPNN interface design (`proteinmpnn_interface_design`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.proteinmpnn_interface_design:ProteinmpnnInterfaceDesignStep`  
**Source:** [`library/seed/src/task/step/steps/proteinmpnn_interface_design.py`](../../library/seed/src/task/step/steps/proteinmpnn_interface_design.py) (407 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Design a binder chain against a fixed partner with the official ProteinMPNN runner, including amino-acid bias, omission and tied

> Interface-focused ProteinMPNN design with chain, bias and tie

关键符号：

- `def parse_bias() (line 31)`
- `def parse_tied_positions() (line 64)`
- `class ProteinmpnnInterfaceDesignStep (line 117)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true, "info": {"missing_code": {"type": ["number", "null"]}}}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `structure_path` | `` | PDB 结构路径 |
| `binder_chains` | `A` | 设计链 |
| `target_chains` | `` | 固定链 |
| `proteinmpnn_path` | `` | ProteinMPNN 仓库路径 |
| `weights_path` | `` | 权重目录 |
| `model_name` | `v_48_020` | 模型; choices: v_48_002, v_48_010, v_48_020, v_48_030 |
| `num_seq_per_target` | `4` | 设计条数; min 1; max 1000 |
| `design_ranges` | `` | 设计区间; advanced |
| `fixed_positions` | `` | 额外固定位置; advanced |
| `bias_aa` | `` | 氨基酸偏好; advanced |
| `omit_aa` | `` | 禁用氨基酸; advanced |
| `tied_positions` | `` | 联动位置; advanced |
| `sampling_temp` | `0.1` | 采样温度; advanced |
| `seed` | `1` | 随机种子; min 1; advanced |
| `device` | `cpu` | 设备; choices: cpu, cuda; advanced |
| `python_executable` | `` | Python 解释器; advanced |
| `timeout_seconds` | `3600` | 超时秒数; min 1; advanced |
| `output` | `` | 输出名称 |

## 2. 用途与解释

Interface-focused ProteinMPNN design with chain, bias and tie controls.

## 3. 正确性依据

**结论：B 级。** 服务器真实运行通过（17.4677 s），1 个步骤产物，首个 sha256 d38886ad26b985e7…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension125.py |
| L3 真实执行 | EXECUTED_SRV | srv:/public/home/lihj/operon715/cov_mpnn2/proteinmpnn_interface_design/output/run_summary.json |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

服务器执行细节：

- 状态：complete，总耗时 17.4677 s，步骤 1。
- 路线：`/path/to/server-worktree/operon715/cov_mpnn2/proteinmpnn_interface_design`；run_id `20261110T142504-3d1d64ddb0c5`。

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
grep '^proteinmpnn_interface_design,' verification/coverage-8.0.1/operator_coverage.csv
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
