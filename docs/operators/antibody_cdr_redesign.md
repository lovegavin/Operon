# CDR 固定框架重设计 (`antibody_cdr_redesign`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.antibody_cdr_redesign:AntibodyCdrRedesignStep`  
**Source:** [`library/seed/src/task/step/steps/antibody_cdr_redesign.py`](../../library/seed/src/task/step/steps/antibody_cdr_redesign.py) (343 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

保持 Kabat CDR 不变，用 ProteinMPNN

> Design antibody framework positions while keeping every Kabat CDR

关键符号：

- `def chain_sequence() (line 28)`
- `def cdr_positions() (line 78)`
- `def fixed_payload() (line 94)`
- `class AntibodyCdrRedesignStep (line 116)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `structure_path` | `` | 结构文件 |
| `proteinmpnn_path` | `` | ProteinMPNN 目录 |
| `weights_path` | `` | 权重目录; advanced |
| `python_executable` | `` | Python 解释器; advanced |
| `model_name` | `v_48_020` | 模型; choices: v_48_002, v_48_010, v_48_020, v_48_030; advanced |
| `num_seq_per_target` | `8` | 设计数量; min 1; max 500 |
| `sampling_temp` | `0.1` | 采样温度 |
| `seed` | `1` | 随机种子; min 0; advanced |
| `chain` | `A` | 抗体链 |
| `device` | `cpu` | 设备; choices: cpu, cuda; advanced |
| `timeout` | `1800` | 超时秒数; min 1; advanced |
| `output` | `designs` | 输出名称; advanced |

## 2. 用途与解释

Design antibody framework positions while keeping every Kabat CDR fixed.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（6.53 s），导出 2 行，产物 sha256 1d8b151acf959fa8…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension179.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/antibody_cdr_redesign |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 6.53 s，导出 2 行。
- 归档路线：`/tmp/ligand_routes/antibody_cdr_redesign`。
- 命令：`cd /home/gavin/Operon-7015-native && /home/gavin/bp-numpy21/bin/python scripts/run.py /tmp/ligand_routes/antibody_cdr_redesign`。

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
grep '^antibody_cdr_redesign,' verification/coverage-8.0.1/operator_coverage.csv
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
