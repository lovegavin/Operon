# LigandMPNN Active Site Design (`ligandmpnn_active_site_design`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.ligandmpnn_active_site_design:LigandmpnnActiveSiteDesignStep`  
**Source:** [`library/seed/src/task/step/steps/ligandmpnn_active_site_design.py`](../../library/seed/src/task/step/steps/ligandmpnn_active_site_design.py) (383 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Find the protein residues around a bound ligand and let the official LigandMPNN redesign only those positions while the rest of the structure stays

> Design only the residues around a bound ligand with the official

关键符号：

- `def parse_structure() (line 30)`
- `def ligand_atoms() (line 70)`
- `def active_site() (line 89)`
- `def protein_residues() (line 127)`
- `def fixed_positions() (line 139)`
- `class LigandmpnnActiveSiteDesignStep (line 146)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `structure_path` | `` | 结构路径 |
| `ligandmpnn_path` | `` | LigandMPNN 仓库 |
| `weights_path` | `` | 权重路径; advanced |
| `python_executable` | `` | Python 解释器; advanced |
| `ligand_resnames` | `LIG` | 配体残基名 |
| `chains` | `` | 设计链; advanced |
| `cutoff` | `8.0` | 活性位点半径; max 20.0 |
| `num_seq_per_target` | `8` | 序列数; min 1; max 500 |
| `temperature` | `0.1` | 采样温度; max 5.0; advanced |
| `seed` | `1` | 随机种子; min 0; advanced |
| `device` | `cpu` | 计算设备; choices: cpu, cuda; advanced |
| `timeout` | `1800` | 超时（秒）; min 10; max 86400; advanced |
| `output` | `designs` | 输出名称; advanced |

## 2. 用途与解释

Design only the residues around a bound ligand with the official LigandMPNN.

Redesign ligand-proximal residues while keeping the rest of the protein fixed.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（4.0476 s），导出 2 行，产物 sha256 f0ccf426d072a192…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension177.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/ligandmpnn_active_site_design |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 4.0476 s，导出 2 行。
- 归档路线：`/tmp/ligand_routes/ligandmpnn_active_site_design`。
- 命令：`run.py /tmp/ligand_routes/ligandmpnn_active_site_design`。

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
grep '^ligandmpnn_active_site_design,' verification/coverage-8.0.1/operator_coverage.csv
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
