# Cophenetic correlation (`cophenetic_correlation`)

**Category:** Statistics  
**Entry point:** `src.task.step.steps.cophenetic_correlation:CopheneticCorrelationStep`  
**Source:** [`library/seed/src/task/step/steps/cophenetic_correlation.py`](../../library/seed/src/task/step/steps/cophenetic_correlation.py) (119 lines)
**Trust level: B — 真实执行（本地或 srv）**

## 1. 代码说明

Pearson correlation between tree patristic and observed sample

> Cophenetic correlation between a tree and a sample distance matrix. The cophenetic distance of two tips is the patristic distance implied by the tree (sum of branch lengths along the path). This operator compares that matrix, in tip order, with an observed sample distance matrix and reports the Pearson correlation, its square, and the number of tips and pairs. It is the equivalent of ``ape::cophenetic.phylo`` followed by ``stats::cor`` with ``method =

关键符号：

- `class CopheneticCorrelationStep (line 24)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(node_dim, field_dim), info=(—)
- 输入 2: ndim=2, numeric=True, dims=(sample_dim, sample_b_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `node_dim` | `node` | Tree node dimension |
| `field_dim` | `field` | Tree field dimension |
| `sample_dim` | `sample` | Sample dimension |
| `sample_b_dim` | `sample_b` | Sample column dimension |
| `output` | `cophenetic_correlation` | Output name |

## 2. 用途与解释

Cophenetic correlation between a tree and a sample distance matrix.

The cophenetic distance of two tips is the patristic distance implied
by the tree (sum of branch lengths along the path). This operator
compares that matrix, in tip order, with an observed sample distance
matrix and reports the Pearson correlation, its square, and the number
of tips and pairs.

It is the equivalent of ``ape::cophenetic.phylo`` followed by
``stats::cor`` with ``method = "pearson"``.

Pearson correlation between tree patristic and observed distances.

## 3. 正确性依据

**结论：B 级。** 真实运行通过（2.99 s），导出 4 行，产物 sha256 c9303c8b2106ff5d…。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension91.py,test_hierarchical_clustering.py,test_r_oracles83.py,test_r_oracles87.py |
| L3 真实执行 | EXECUTED | verification/coverage-8.0.1/routes/cophenetic_correlation |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

本次执行细节：

- 状态：PASS，耗时 2.99 s，导出 4 行。
- 归档路线：`/tmp/cov_stats/cophenetic_correlation`。
- 命令：`cd /path/to/Operon-worktree && python scripts/run.py /tmp/cov_stats/cophenetic_correlation --check && python scripts/run.py /tmp/cov_stats/cophenetic_correlation`。

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
grep '^cophenetic_correlation,' verification/coverage-8.0.1/operator_coverage.csv
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
