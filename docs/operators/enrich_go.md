# enrich_go (`enrich_go`)

**Category:** analysis  
**Entry point:** `src.task.step.steps.enrich_go:EnrichGoStep`  
**Source:** [`library/seed/src/task/step/steps/enrich_go.py`](../../library/seed/src/task/step/steps/enrich_go.py) (278 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Hypergeometric enrichment of one term axis over two

> GO term enrichment by the hypergeometric test. Given a hit set and a background universe, both expressed as binary gene x term matrices, this step computes for every term: N total genes in the universe n total genes in the hit set K genes annotated to the term in the universe k genes annotated to the term in the hit set expected n * K / N P P(X >= k | hypergeometric(N, K, n)) Q P adjusted by the requested multiple-testing method The output is a term x statistic matrix, one row per term retained. Layout ------ hits dims: [gene_dim, term_dim] universe dims: [gene_dim, term_dim] output dims:…

关键符号：

- `class EnrichGoStep (line 50)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(gene_dim, term_dim), info=(—)
- 输入 2: ndim=2, numeric=True, dims=(gene_dim, term_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `gene_dim` | `gene` | Gene dimension |
| `term_dim` | `go_term` | Term dimension |
| `correction` | `fdr` | Multiple-testing correction; choices: fdr, bonferroni, holm, hommel, fdr_by |
| `min_term_size` | `1` | Minimum term size; min 1 |
| `output` | `` | Output key |

## 2. 用途与解释

GO term enrichment by the hypergeometric test.

Given a hit set and a background universe, both expressed as binary
gene x term matrices, this step computes for every term:

N          total genes in the universe
n          total genes in the hit set
K          genes annotated to the term in the universe
k          genes annotated to the term in the hit set
expected   n * K / N
P          P(X >= k | hypergeometric(N, K, n))
Q          P adjusted by the requested multiple-testing method

The output is a term x statistic matrix, one row per term retained.

Layout
------
hits       dims: [gene_dim, term_dim]
universe   dims: [gene_dim, term_dim]
output     dims: [term_dim, "statistic"]

Both inputs must share the same term labels. The hit set's genes
must be a subset of the universe's genes; otherwise the caller must
restrict the universe first.

Params:
gene_dim       : name of the gene di

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_operator_metadata.py |
| L3 真实执行 | ROUTE | operator_table.csv:builtin_route |
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
grep '^enrich_go,' verification/coverage-8.0.1/operator_coverage.csv
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
