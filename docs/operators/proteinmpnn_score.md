# ProteinMPNN sequence score (`proteinmpnn_score`)

**Category:** Machine Learning  
**Entry point:** `src.task.step.steps.proteinmpnn_score:ProteinmpnnScoreStep`  
**Source:** [`library/seed/src/task/step/steps/proteinmpnn_score.py`](../../library/seed/src/task/step/steps/proteinmpnn_score.py) (285 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Score a structure/sequence pair with the official ProteinMPNN runner in --score_only mode; returns mean and global negative log-likelihood per

> ProteinMPNN score-only evaluation of structure/sequence

关键符号：

- `def parse_fasta() (line 22)`
- `def score_files() (line 66)`
- `def summarize() (line 80)`
- `class ProteinmpnnScoreStep (line 96)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true, "info": {"missing_code": {"type": ["number", "null"]}}}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `structure_path` | `` | 结构文件 |
| `fasta_path` | `` | 待打分序列 |
| `proteinmpnn_path` | `` | ProteinMPNN 仓库路径 |
| `weights_path` | `` | 权重目录; advanced |
| `model_name` | `v_48_020` | 权重版本; choices: v_48_002, v_48_010, v_48_020, v_48_030; advanced |
| `chains` | `` | 链选择; advanced |
| `python_executable` | `` | Python 解释器; advanced |
| `seed` | `1` | 随机种子; min 0; advanced |
| `device` | `cpu` | 计算设备; choices: cpu, cuda; advanced |
| `timeout_seconds` | `1800` | 超时（秒）; min 1; advanced |
| `output` | `scores` | 输出名称; advanced |

## 2. 用途与解释

ProteinMPNN score-only evaluation of structure/sequence pairs.

## 3. 正确性依据

**结论：B 级。** 服务器真实运行通过（11.1892 s），1 个步骤产物，首个 sha256 54b82c0515e15a60…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension121.py,test_extension163.py |
| L3 真实执行 | EXECUTED_SRV | srv:/public/home/lihj/operon715/closure_replay/proteinmpnn_score/output/run_summary.json |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

服务器执行细节：

- 状态：complete，总耗时 11.1892 s，步骤 1。
- 路线：`/public/home/lihj/operon715/closure_replay/proteinmpnn_score`；run_id `20261110T125314-71564253a91e`。

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
grep '^proteinmpnn_score,' verification/coverage-8.0.1/operator_coverage.csv
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
