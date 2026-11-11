# Foldseek structural clustering (`foldseek_cluster`)

**Category:** Structure  
**Entry point:** `src.task.step.steps.foldseek_cluster:FoldseekClusterStep`  
**Source:** [`library/seed/src/task/step/steps/foldseek_cluster.py`](../../library/seed/src/task/step/steps/foldseek_cluster.py) (194 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Cluster a directory of structures with Foldseek and report cluster membership, size and

> foldseek_cluster: structural clustering with

关键符号：

- `def collect_structures() (line 21)`
- `def run_cluster() (line 46)`
- `def cluster_rows() (line 96)`
- `class FoldseekClusterStep (line 117)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `structure_dir` | `` | 结构目录 |
| `structure_paths` | `` | 结构文件列表（逗号分隔） |
| `foldseek_path` | `foldseek` | Foldseek 可执行文件 |
| `tmscore_threshold` | `0.6` | TM-score 阈值; min 0.0; max 1.0 |
| `coverage` | `0.8` | 覆盖度; min 0.0; max 1.0 |
| `timeout_seconds` | `600` | 超时 (秒); min 10; max 7200 |
| `output` | `clusters` | 输出参数名 |

## 2. 用途与解释

foldseek_cluster: structural clustering with Foldseek.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（2.325 s），导出 None 行，产物 sha256 05f822852816ecc1…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_l2_gap.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/foldseek_cluster |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 2.325 s，导出 None 行。
- 归档路线：`/tmp/l2_routes/foldseek_cluster`。
- 命令：`scripts/run.py /tmp/l2_routes/foldseek_cluster`。

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
grep '^foldseek_cluster,' verification/coverage-8.0.1/operator_coverage.csv
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
