# GSVA PLAGE scores (`gsva_plage`)

**Category:** Omics  
**Entry point:** `src.task.step.steps.gsva_plage:GsvaPlageStep`  
**Source:** [`library/seed/src/task/step/steps/gsva_plage.py`](../../library/seed/src/task/step/steps/gsva_plage.py) (155 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

PLAGE gene-set scores: first right singular vector of the gene-wise z-scored expression of each set (GSVA plage

> PLAGE gene-set scores following the GSVA implementation. PLAGE (Pathway Level Analysis of Gene Expression) scores a gene set by the first right singular vector of the gene-wise standardized expression matrix restricted to the set. GSVA's ``plage`` method is: Z <- t(scale(t(X))) # gene-wise z-score across samples for each set: svd(Z[set, ])$v[, 1] This operator reproduces that computation. The singular-vector sign is not identified by SVD, so scores are normalized to make the largest-magnitude loading positive; comparisons with R GSVA are therefore exact up to a per-set sign

关键符号：

- `class GsvaPlageStep (line 26)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(feature_dim, sample_dim), info=(—)
- 输入 2: ndim=2, numeric=True, dims=(gene_dim, gene_set_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `feature_dim` | `feature` | 特征维度 |
| `sample_dim` | `sample` | 样本维度 |
| `gene_dim` | `gene` | Gene Dim |
| `gene_set_dim` | `gene_set` | Gene Set Dim |
| `min_size` | `1` | Min Size; min 1 |
| `output` | `` | 输出名称 |

## 2. 用途与解释

PLAGE gene-set scores following the GSVA implementation.

PLAGE (Pathway Level Analysis of Gene Expression) scores a gene set by
the first right singular vector of the gene-wise standardized
expression matrix restricted to the set. GSVA's ``plage`` method is:

Z <- t(scale(t(X)))          # gene-wise z-score across samples
for each set: svd(Z[set, ])$v[, 1]

This operator reproduces that computation. The singular-vector sign is
not identified by SVD, so scores are normalized to make the
largest-magnitude loading positive; comparisons with R GSVA are
therefore exact up to a per-set sign flip.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_extension90.py,test_r_oracles86.py |
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
grep '^gsva_plage,' verification/coverage-8.0.1/operator_coverage.csv
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
