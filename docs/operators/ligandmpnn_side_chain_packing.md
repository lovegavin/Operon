# LigandMPNN side-chain packing (`ligandmpnn_side_chain_packing`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.ligandmpnn_side_chain_packing:LigandmpnnSideChainPackingStep`  
**Source:** [`library/seed/src/task/step/steps/ligandmpnn_side_chain_packing.py`](../../library/seed/src/task/step/steps/ligandmpnn_side_chain_packing.py) (211 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Run the official LigandMPNN side-chain packer on a backbone PDB and return the packed structure as an atom table. The packer needs the LigandMPNN repository and its side-chain

> Side-chain packing through the official LigandMPNN

关键符号：

- `class LigandmpnnSideChainPackingStep (line 23)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `structure_path` | `` | 结构文件 |
| `ligandmpnn_path` | `` | LigandMPNN 目录 |
| `weights_path` | `` | 权重目录 |
| `checkpoint` | `ligandmpnn_v_32_010_25.pt` | 设计权重 |
| `sc_checkpoint` | `ligandmpnn_sc_v_32_002_16.pt` | 侧链权重 |
| `model_type` | `ligand_mpnn` | 模型类型; choices: protein_mpnn, ligand_mpnn, per_residue_label_membrane_mpnn, global_label_membrane_mpnn, soluble_mpnn |
| `chains` | `` | 链 |
| `number_of_packs_per_design` | `1` | 装包次数; min 1; max 16 |
| `repack_everything` | `False` | 全部重装 |
| `packed_suffix` | `_packed` | 装包后缀 |
| `seed` | `0` | 随机种子; min 0; max 100000 |
| `device` | `cpu` | 设备; choices: cpu, cuda |
| `python_executable` | `` | Python 解释器 |
| `timeout_seconds` | `1800` | 超时; min 30; max 86400 |
| `output` | `packed` | 输出参数 |

## 2. 用途与解释

Side-chain packing through the official LigandMPNN packer.

Pack side chains of a fixed backbone with the LigandMPNN packer.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（477.875 s），导出 None 行，产物 sha256 318f149d65f8f71f…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension263.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/ligandmpnn_side_chain_packing |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 477.875 s，导出 None 行。
- 归档路线：`/tmp/ligandmpnn_sc2`。
- 命令：`scripts/run.py <archived route>`。

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
grep '^ligandmpnn_side_chain_packing,' verification/coverage-8.0.1/operator_coverage.csv
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
