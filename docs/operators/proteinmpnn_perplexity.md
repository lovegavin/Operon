# ProteinMPNN Perplexity (`proteinmpnn_perplexity`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.proteinmpnn_perplexity:ProteinmpnnPerplexityStep`  
**Source:** [`library/seed/src/task/step/steps/proteinmpnn_perplexity.py`](../../library/seed/src/task/step/steps/proteinmpnn_perplexity.py) (329 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Computes how uncertain ProteinMPNN is at every designed position. The operator runs the official conditional-probability pass and reports the effective number of amino-acid choices, the position entropy and the most likely

> ProteinMPNN per-position perplexity from conditional

关键符号：

- `def parse_native() (line 29)`
- `def native_from_tokens() (line 48)`
- `def probability_matrix() (line 70)`
- `def perplexity_rows() (line 96)`
- `def most_likely() (line 108)`
- `def designer_command() (line 113)`
- `def run_designer() (line 150)`
- `class ProteinmpnnPerplexityStep (line 207)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `structure_path` | `` | 结构文件路径 |
| `proteinmpnn_path` | `` | ProteinMPNN 仓库路径 |
| `weights_path` | `` | 权重路径 |
| `python_executable` | `` | Python 解释器 |
| `model_name` | `v_48_020` | 模型名称; choices: v_48_002, v_48_010, v_48_020, v_48_030 |
| `num_seq_per_target` | `8` | 概率批次数; min 1; max 64 |
| `seed` | `1` | 随机种子; min 0; advanced |
| `chains` | `` | 链; advanced |
| `device` | `cpu` | 设备; choices: cpu, cuda; advanced |
| `timeout` | `1800` | 超时（秒）; min 1; advanced |
| `position_dim` | `position` | 位点维度; advanced |
| `output` | `perplexity` | 输出名称 |

## 2. 用途与解释

ProteinMPNN per-position perplexity from conditional probabilities.

Per-position ProteinMPNN perplexity from conditional amino-acid probabilities.

## 3. 正确性依据

**结论：B 级。** 服务器真实运行通过（193.2579 s），1 个步骤产物，首个 sha256 83fff62e14d6b6ba…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension190.py,test_extension359.py |
| L3 真实执行 | EXECUTED_SRV | srv:/public/home/lihj/operon715/cov_mpnn/proteinmpnn_perplexity/output/run_summary.json |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

服务器执行细节：

- 状态：complete，总耗时 193.2579 s，步骤 1。
- 路线：`/path/to/server-worktree/operon715/cov_mpnn/proteinmpnn_perplexity`；run_id `20261110T135730-9ce61839ce6f`。

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
grep '^proteinmpnn_perplexity,' verification/coverage-8.0.1/operator_coverage.csv
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
