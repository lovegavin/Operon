# tRNAscan-SE tRNA genes (`trnascan_se`)

**Category:** Genome  
**Entry point:** `src.task.step.steps.trnascan_se:TrnascanSeStep`  
**Source:** [`library/seed/src/task/step/steps/trnascan_se.py`](../../library/seed/src/task/step/steps/trnascan_se.py) (193 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Detect tRNA genes with the official tRNAscan-SE binary; returns coordinates, isotype, anticodon, intron bounds and

> tRNA gene detection through the official tRNAscan-SE

关键符号：

- `def write_fasta() (line 29)`
- `def parse_output() (line 38)`
- `def run_trnascan() (line 70)`
- `class TrnascanSeStep (line 119)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sequence_dim, position_dim), info=(representation)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true, "info": {"missing_code": {"type": ["number", "null"]}}}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sequence_dim` | `sequence` | 序列维度 |
| `position_dim` | `position` | 位置维度 |
| `trnascan_path` | `tRNAscan-SE` | tRNAscan-SE 可执行文件 |
| `mode` | `general` | 搜索模式; choices: general, bacterial, archaeal, eukaryotic |
| `timeout_seconds` | `900` | 超时 (秒); min 30; max 21600 |
| `output` | `trnas` | 输出参数名 |

## 2. 用途与解释

tRNA gene detection through the official tRNAscan-SE binary.

## 3. 正确性依据

**结论：B 级。** 服务器真实运行通过（0.2921 s），1 个步骤产物，首个 sha256 ee6dc64df8b4753f…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension352.py,test_remote_install_readiness.py |
| L3 真实执行 | EXECUTED_SRV | srv:/public/home/lihj/operon715/closure_replay/trnascan_se/output/run_summary.json |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

服务器执行细节：

- 状态：complete，总耗时 0.2921 s，步骤 1。
- 路线：`/path/to/server-worktree/operon715/closure_replay/trnascan_se`；run_id `20261110T123431-7d0c718908f7`。

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
grep '^trnascan_se,' verification/coverage-8.0.1/operator_coverage.csv
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
