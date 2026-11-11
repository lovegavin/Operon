# HMMER domain annotation (`hmmer_domains`)

**Category:** Sequence  
**Entry point:** `src.task.step.steps.hmmer_domains:HmmerDomainsStep`  
**Source:** [`library/seed/src/task/step/steps/hmmer_domains.py`](../../library/seed/src/task/step/steps/hmmer_domains.py) (285 lines)  
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Annotate protein sequences with Pfam/HMMER domains through the official hmmscan binary and return one row per domain

> Pfam/HMMER domain annotation through the official hmmscan

关键符号：

- `def write_fasta() (line 30)`
- `def parse_domtbl() (line 39)`
- `def run_hmmscan() (line 74)`
- `class HmmerDomainsStep (line 159)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sequence_dim, position_dim), info=(representation)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true, "info": {"missing_code": {"type": ["number", "null"]}}}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sequence_dim` | `sequence` | 序列维 |
| `position_dim` | `position` | 位置维 |
| `hmm_path` | `` | HMM 数据库 |
| `hmmscan_path` | `hmmscan` | hmmscan 路径 |
| `cpu` | `1` | CPU 线程; min 1; max 64 |
| `timeout_seconds` | `1800` | 超时 (秒); min 30; max 14400 |
| `output` | `domains` | 输出名 |

## 2. 用途与解释

Pfam/HMMER domain annotation through the official hmmscan binary.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（1.77 s），导出 None 行，产物 sha256 n/a…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension253.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/hmmer_domains |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 1.77 s，导出 None 行。
- 归档路线：`/tmp/cov_sequence/hmmer_domains`。
- 命令：`/home/gavin/bp-numpy21/bin/python scripts/run.py /tmp/cov_sequence/hmmer_domains`。

服务器执行细节：

- 状态：complete，总耗时 0.2256 s，步骤 1。
- 路线：`/public/home/lihj/operon715/closure_replay/hmmer_domains`；run_id `20261110T123357-97e7944729df`。

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
grep '^hmmer_domains,' verification/coverage-8.0.1/operator_coverage.csv
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
