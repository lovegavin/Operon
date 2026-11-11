# ESM-3 逆折叠序列设计 (`esm3_inverse_folding`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.esm3_inverse_folding:Esm3InverseFoldingStep`  
**Source:** [`library/seed/src/task/step/steps/esm3_inverse_folding.py`](../../library/seed/src/task/step/steps/esm3_inverse_folding.py) (196 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Design a sequence for a protein backbone with the official ESM-3 open model, using coordinates as the only condition, and report recovery against the native sequence when it is

> esm3_inverse_folding: structure-conditioned sequence design with

关键符号：

- `def load_model() (line 18)`
- `def chain_pdb() (line 40)`
- `def three_to_one() (line 55)`
- `def native_sequence() (line 61)`
- `def recovery() (line 75)`
- `def design_rows() (line 82)`
- `class Esm3InverseFoldingStep (line 96)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": false}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `structure_path` | `` | 主链结构 (PDB) |
| `chain` | `A` | 链 |
| `num_steps` | `20` | 生成步数; min 1; max 200 |
| `temperature` | `1.0` | 温度; min 0.01; max 5.0 |
| `device` | `cpu` | 计算设备; choices: cpu, cuda |
| `design_dim` | `design` | 输出维度名 |
| `output` | `designs` | 输出参数名 |

## 2. 用途与解释

esm3_inverse_folding: structure-conditioned sequence design with ESM-3.

## 3. 正确性依据

**结论：B 级。** 服务器真实运行通过（384.6429 s），1 个步骤产物，首个 sha256 c6bb7609d3b47457…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension326.py |
| L3 真实执行 | EXECUTED_SRV | srv:/public/home/lihj/operon715/cov_ml3/esm3_inverse_folding/output/run_summary.json |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

服务器执行细节：

- 状态：complete，总耗时 384.6429 s，步骤 1。
- 路线：`/path/to/server-worktree/operon715/cov_ml3/esm3_inverse_folding`；run_id `20261110T135920-c28b68a988b0`。

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
grep '^esm3_inverse_folding,' verification/coverage-8.0.1/operator_coverage.csv
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
