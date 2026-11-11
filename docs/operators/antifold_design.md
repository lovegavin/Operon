# AntiFold 抗体逆折叠设计 (`antifold_design`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.antifold_design:AntifoldDesignStep`  
**Source:** [`library/seed/src/task/step/steps/antifold_design.py`](../../library/seed/src/task/step/steps/antifold_design.py) (286 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Run the official AntiFold antibody inverse-folding model on a PDB structure, returning sampled sequences with scores and a per-residue log-probability

> antifold_design: AntiFold antibody inverse-folding

关键符号：

- `def parse_fasta() (line 23)`
- `def parse_profile() (line 63)`
- `def profile_summary() (line 98)`
- `def antifold_command() (line 110)`
- `def run_antifold() (line 163)`
- `class AntifoldDesignStep (line 184)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": false}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `structure_path` | `` | 结构文件 (PDB) |
| `nanobody_chain` | `` | 纳米抗体链 |
| `heavy_chain` | `` | 重链 |
| `light_chain` | `` | 轻链 |
| `antigen_chain` | `` | 抗原链 |
| `regions` | `CDR1 CDR2 CDR3` | 采样区域 |
| `num_seq_per_target` | `5` | 每个目标的序列数; min 1; max 50 |
| `sampling_temp` | `0.2` | 采样温度 |
| `seed` | `42` | 随机种子; min 0; max 1000000 |
| `limit_variation` | `False` | 限制变异 |
| `python_executable` | `` | Python 解释器 |
| `timeout_seconds` | `1800` | 超时 (秒); min 30; max 7200 |
| `design_dim` | `design` | 设计维度名 |
| `output` | `designs` | 输出参数名 |
| `runner_path` | `` | 自定义 runner 路径（可选） |

## 2. 用途与解释

antifold_design: AntiFold antibody inverse-folding redesign.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（20.9099 s），导出 None 行，产物 sha256 n/a…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension300.py,test_remote_provision.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/antifold_design |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 20.9099 s，导出 None 行。
- 归档路线：`/tmp/antifold_design_paired2`。
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
grep '^antifold_design,' verification/coverage-8.0.1/operator_coverage.csv
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
