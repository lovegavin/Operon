# AMRFinderPlus resistance genes (`amrfinder_plus`)

**Category:** Genome  
**Entry point:** `src.task.step.steps.amrfinder_plus:AmrfinderPlusStep`  
**Source:** [`library/seed/src/task/step/steps/amrfinder_plus.py`](../../library/seed/src/task/step/steps/amrfinder_plus.py) (271 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Detect antimicrobial resistance and virulence genes with the official AMRFinderPlus binary; returns gene family, class, coordinates, identity and

> AMR and virulence gene detection through the official AMRFinderPlus

关键符号：

- `def write_fasta() (line 53)`
- `def parse_report() (line 76)`
- `def run_amrfinder() (line 127)`
- `class AmrfinderPlusStep (line 177)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(sequence_dim, position_dim), info=(representation)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true, "info": {"missing_code": {"type": ["number", "null"]}}}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `sequence_dim` | `sequence` | 序列维度 |
| `position_dim` | `position` | 位置维度 |
| `amrfinder_path` | `amrfinder` | amrfinder 可执行文件 |
| `database_dir` | `` | AMRFinder 数据库目录 |
| `mode` | `protein` | 输入类型; choices: protein, nucleotide |
| `organism` | `` | 物种分组 |
| `threads` | `1` | 线程数; min 1; max 64 |
| `timeout_seconds` | `1800` | 超时 (秒); min 30; max 21600 |
| `output` | `hits` | 输出参数名 |

## 2. 用途与解释

AMR and virulence gene detection through the official AMRFinderPlus binary.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（2.76 s），导出 None 行，产物 sha256 n/a…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension353.py,test_remote_install_readiness.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/amrfinder_plus |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 2.76 s，导出 None 行。
- 归档路线：`/tmp/cov_sequence/amrfinder_plus`。
- 命令：`python scripts/run.py /tmp/cov_sequence/amrfinder_plus`。

服务器执行细节：

- 状态：complete，总耗时 1.4639 s，步骤 1。
- 路线：`/path/to/server-worktree/operon715/closure_replay/amrfinder_plus`；run_id `20261110T123704-e71af8404975`。

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
grep '^amrfinder_plus,' verification/coverage-8.0.1/operator_coverage.csv
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
