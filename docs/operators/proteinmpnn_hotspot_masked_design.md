# Hotspot-masked design (`proteinmpnn_hotspot_masked_design`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.proteinmpnn_hotspot_masked_design:ProteinmpnnHotspotMaskedDesignStep`  
**Source:** [`library/seed/src/task/step/steps/proteinmpnn_hotspot_masked_design.py`](../../library/seed/src/task/step/steps/proteinmpnn_hotspot_masked_design.py) (257 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Rank binder-target interface residues by contact density, keep the top hotspots as the only designable positions and run the official ProteinMPNN runner with every other residue

> Redesign interface hotspots with ProteinMPNN fixed

关键符号：

- `def hotspot_table() (line 21)`
- `def hotspot_mask() (line 61)`
- `class ProteinmpnnHotspotMaskedDesignStep (line 73)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(atom_dim, field_dim), info=(encoders)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `atom_dim` | `atom` | 原子维度 |
| `field_dim` | `field` | 字段维度 |
| `structure_path` | `` | 结构文件 |
| `binder_chains` | `` | 抗体链 |
| `target_chains` | `` | 抗原链 |
| `cutoff` | `5.0` | 接触截断; min 3.0; max 10.0 |
| `min_contacts` | `1` | 最少接触数; min 1; max 20 |
| `top_n` | `0` | 热点数量; min 0; max 1000 |
| `proteinmpnn_path` | `` | ProteinMPNN 目录 |
| `weights_path` | `` | 权重目录 |
| `python_executable` | `` | Python 解释器 |
| `num_seq_per_target` | `8` | 序列数量; min 1; max 128 |
| `sampling_temp` | `0.1` | 采样温度 |
| `seed` | `1` | 随机种子; min 0; max 2147483647 |
| `model_name` | `v_48_020` | 模型; choices: v_48_002, v_48_010, v_48_020, v_48_030 |
| `device` | `cpu` | 设备; choices: cpu, cuda |
| `timeout` | `1800` | 超时; min 1; max 86400 |
| `output` | `designs` | 输出名 |

## 2. 用途与解释

Redesign interface hotspots with ProteinMPNN fixed positions.

Design the hotspot residues of a binder-target interface.

## 3. 正确性依据

**结论：B 级。** 服务器真实运行通过（9.5176 s），1 个步骤产物，首个 sha256 c87dd550a9798344…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension258.py |
| L3 真实执行 | EXECUTED_SRV | srv:/public/home/lihj/operon715/cov_mpnn3/proteinmpnn_hotspot_masked_design/output/run_summary.json |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

服务器执行细节：

- 状态：complete，总耗时 9.5176 s，步骤 1。
- 路线：`/public/home/lihj/operon715/cov_mpnn3/proteinmpnn_hotspot_masked_design`；run_id `20261110T143626-5b25e45adc42`。

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
grep '^proteinmpnn_hotspot_masked_design,' verification/coverage-8.0.1/operator_coverage.csv
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
