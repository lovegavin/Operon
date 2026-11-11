# LigandMPNN Design (`ligandmpnn_design`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.ligandmpnn_design:LigandMpnnDesignStep`  
**Source:** [`library/seed/src/task/step/steps/ligandmpnn_design.py`](../../library/seed/src/task/step/steps/ligandmpnn_design.py) (342 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Design protein sequences on a fixed backbone with the official LigandMPNN runner, including ligand- and side-chain-aware context, per-residue bias, omitted residues and redesign

> Sequence design with the official LigandMPNN

关键符号：

- `def parse_design_fasta() (line 55)`
- `class LigandMpnnDesignStep (line 131)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `structure_path` | `` | 结构文件路径 |
| `ligandmpnn_path` | `` | LigandMPNN 目录 |
| `weights_path` | `` | 权重文件路径 |
| `python_executable` | `` | Python 解释器; advanced |
| `model_type` | `ligand_mpnn` | 模型类型; choices: ligand_mpnn, protein_mpnn, soluble_mpnn |
| `chains_to_design` | `` | 设计链 |
| `fixed_positions` | `` | 固定残基; advanced |
| `redesigned_residues` | `` | 仅重设计残基; advanced |
| `omit_AA` | `` | 禁用氨基酸; advanced |
| `bias_AA` | `` | 氨基酸偏好; advanced |
| `temperature` | `0.1` | 采样温度; min 0.01; max 5.0 |
| `number_of_batches` | `1` | 采样批次数; min 1; max 100 |
| `batch_size` | `1` | 批大小; min 1; max 64; advanced |
| `seed` | `1` | 随机种子; min 0; max 2147483647; advanced |
| `ligand_mpnn_use_atom_context` | `True` | 使用配体上下文; advanced |
| `ligand_mpnn_cutoff_for_score` | `8.0` | 配体上下文半径 (Å); min 0.1; max 20.0; advanced |
| `ligand_mpnn_use_side_chain_context` | `False` | 使用侧链上下文; advanced |
| `device` | `cpu` | 设备; choices: cpu, cuda |
| `timeout_seconds` | `3600` | 超时 (秒); min 1; max 86400; advanced |
| `output` | `output` | 输出端口; advanced |

## 2. 用途与解释

Sequence design with the official LigandMPNN runner.

## 3. 正确性依据

**结论：B 级。** 服务器真实运行通过（966.847 s），1 个步骤产物，首个 sha256 91b3828c9960ac8d…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension132.py,test_extension134.py |
| L3 真实执行 | EXECUTED_SRV | srv:/public/home/lihj/operon715/closure_replay/ligandmpnn_design/output/run_summary.json |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

服务器执行细节：

- 状态：complete，总耗时 966.847 s，步骤 1。
- 路线：`/public/home/lihj/operon715/closure_replay/ligandmpnn_design`；run_id `20261110T140157-52f0beeed956`。

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
grep '^ligandmpnn_design,' verification/coverage-8.0.1/operator_coverage.csv
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
