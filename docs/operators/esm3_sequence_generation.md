# ESM-3 序列生成 (`esm3_sequence_generation`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.esm3_sequence_generation:Esm3SequenceGenerationStep`  
**Source:** [`library/seed/src/task/step/steps/esm3_sequence_generation.py`](../../library/seed/src/task/step/steps/esm3_sequence_generation.py) (190 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Sample protein sequences from an ESM-3 masked prompt on CPU or

> ESM-3 sequence generation with masked

关键符号：

- `def parse_prompt() (line 19)`
- `def mask_positions() (line 39)`
- `def load_model() (line 45)`
- `def generate_sequence() (line 65)`
- `def encode_generated() (line 88)`
- `class Esm3SequenceGenerationStep (line 97)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"dims": ["sequence", "position"], "columns": [], "labels": {}}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `prompt` | `MKTAYIAKQR________` | 提示序列 |
| `num_steps` | `8` | 采样步数; min 1; max 64 |
| `temperature` | `0.7` | 采样温度; min 0.05; max 2.0 |
| `seed` | `0` | 随机种子 |
| `model` | `esm3_sm_open_v1` | 模型名称 |
| `device` | `cpu` | 设备; choices: cpu, cuda |
| `output` | `generation` | 输出 |

## 2. 用途与解释

ESM-3 sequence generation with masked prompts.

Sample a protein sequence from an ESM-3 masked prompt.

## 3. 正确性依据

**结论：B 级。** 服务器真实运行通过（186.0743 s），1 个步骤产物，首个 sha256 abcf8a17c23c9fc0…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension348.py |
| L3 真实执行 | EXECUTED_SRV | srv:/public/home/lihj/operon715/cov_ml3/esm3_sequence_generation/output/run_summary.json |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

服务器执行细节：

- 状态：complete，总耗时 186.0743 s，步骤 1。
- 路线：`/public/home/lihj/operon715/cov_ml3/esm3_sequence_generation`；run_id `20261110T135223-35f23ad7522c`。

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
grep '^esm3_sequence_generation,' verification/coverage-8.0.1/operator_coverage.csv
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
