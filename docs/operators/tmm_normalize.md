# TMM normalization (`tmm_normalize`)

**Category:** Data  
**Entry point:** `src.task.step.steps.tmm_normalize:TmmNormalizeStep`  
**Source:** [`library/seed/src/task/step/steps/tmm_normalize.py`](../../library/seed/src/task/step/steps/tmm_normalize.py) (175 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Normalize a count matrix with edgeR-style TMM

> Trimmed mean of M-values (TMM) normalization. This is an independent Python implementation of the TMM method from edgeR. Counts are scaled by effective library sizes effective_library_size = library_size * norm_factor and converted to counts per ``target_sum``. The implementation follows edgeR's reference-sample selection, trimmed log-ratio mean and optional inverse-variance weighting, but is not a wrapper around

关键符号：

- `class TmmNormalizeStep (line 23)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(feature_dim, sample_dim), info=(—)
- 输出: mode=transform, schema={}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `feature_dim` | `feature` | 特征维度 |
| `sample_dim` | `sample` | 样本维度 |
| `target_sum` | `1000000.0` | 目标总量 |
| `logratio_trim` | `0.3` | Logratio Trim; min 0 |
| `sum_trim` | `0.05` | Sum Trim; min 0 |
| `do_weighting` | `True` | Do Weighting |
| `output` | `` | 输出名称 |

## 2. 用途与解释

Trimmed mean of M-values (TMM) normalization.

This is an independent Python implementation of the TMM method from
edgeR. Counts are scaled by effective library sizes

effective_library_size = library_size * norm_factor

and converted to counts per ``target_sum``. The implementation follows
edgeR's reference-sample selection, trimmed log-ratio mean and optional
inverse-variance weighting, but is not a wrapper around R.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension12.py,test_r_oracles4.py |
| L3 真实执行 | ROUTE | operator_table.csv:generated_route |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。
- 注意：该算子没有独立数值 oracle， correctness 仅到“契约/测试/执行”层级。

## 4. 限制与失败模式

Declared memory modes: full. Operon retains the existing planner, disk-backed
inputs and emergency spill behavior; full-mode operators still require their
declared working set. This generated reference has not been independently
scientifically reviewed.

## 5. 复现

```bash
cd /path/to/Operon-worktree
python -m operon registry check --json
grep '^tmm_normalize,' verification/coverage-8.0.1/operator_coverage.csv
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
