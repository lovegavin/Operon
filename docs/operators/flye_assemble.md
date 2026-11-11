# Flye de novo assembly (`flye_assemble`)

**Category:** Genome  
**Entry point:** `src.task.step.steps.flye_assemble:FlyeAssembleStep`  
**Source:** [`library/seed/src/task/step/steps/flye_assemble.py`](../../library/seed/src/task/step/steps/flye_assemble.py) (336 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Assemble long reads de novo with the official Flye binary and report contig lengths, coverage and

> De novo long-read assembly through the official Flye

关键符号：

- `def write_fasta() (line 31)`
- `def parse_fasta() (line 42)`
- `def parse_assembly_info() (line 64)`
- `def n50() (line 98)`
- `def tool_environment() (line 113)`
- `def run_flye() (line 122)`
- `class FlyeAssembleStep (line 195)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sequence_dim, position_dim), info=(representation)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true, "info": {"missing_code": {"type": ["number", "null"]}}}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sequence_dim` | `sequence` | 序列维度 |
| `position_dim` | `position` | 位置维度 |
| `mode` | `nano-raw` | 读长类型; choices: nano-raw, nano-corr, nano-hq, pacbio-raw, pacbio-corr, pacbio-hifi |
| `genome_size` | `48k` | 基因组大小 |
| `threads` | `4` | 线程数; min 1; max 128 |
| `min_overlap` | `1000` | 最小重叠长度; min 100; max 100000 |
| `flye_path` | `flye` | Flye 可执行文件 |
| `timeout_seconds` | `1800` | 超时 (秒); min 30; max 86400 |
| `output` | `assembly` | 输出参数名 |

## 2. 用途与解释

De novo long-read assembly through the official Flye binary.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（51.87 s），导出 None 行，产物 sha256 0b9012dea462b7cf…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension354.py,test_remote_install_readiness.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/flye_assemble |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 51.87 s，导出 None 行。
- 归档路线：`/tmp/cov_sequence/flye_assemble`。
- 命令：`python scripts/run.py /tmp/cov_sequence/flye_assemble`。

服务器执行细节：

- 状态：complete，总耗时 93.1894 s，步骤 1。
- 路线：`/path/to/server-worktree/operon715/closure_replay/flye_assemble`；run_id `20261110T123221-3e8693c722a2`。

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
grep '^flye_assemble,' verification/coverage-8.0.1/operator_coverage.csv
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
