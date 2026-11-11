# PCA / PCoA / UMAP / t-SNE (`reduce`)

**Category:** 统计分析  
**Entry point:** `src.task.step.steps.reduce:ReduceStep`  
**Source:** [`library/seed/src/task/step/steps/reduce.py`](../../library/seed/src/task/step/steps/reduce.py) (438 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Reduce one axis of a 2D form to a small number of

> Dimensionality reduction along one axis of a form. Compresses one axis of a 2D form into a small number of components. The other axis becomes the observation axis of the output. Two kinds of input ------------------ 1. Feature matrix ``[feature, sample]`` (or the reverse). The operator compresses the feature axis into components. Methods: ``pca``, ``umap``, ``tsne``. 2. Square distance matrix ``[sample, sample_b]`` (produced by ``distance_matrix``). The operator computes principal coordinates of the distance matrix. Method: ``pcoa``. The output always has the form:: dims = [<observation_dim>,…

关键符号：

- `class ReduceStep (line 78)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(dim), info=(—)
- 输出: mode=choose, schema={}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `dim` | `` | — |
| `method` | `pca` | choices: pca, pcoa, umap, tsne |
| `n_components` | `` | Omit for method default: PCA/PCoA 10, UMAP/t-SNE; min 1 |
| `standardize` | `True` | — |
| `random_state` | `0` | — |
| `n_neighbors` | `` | min 2 |
| `min_dist` | `` | min 0 |
| `metric` | `` | — |
| `perplexity` | `` | — |
| `learning_rate` | `` | — |
| `n_iter` | `` | min 250 |

## 2. 用途与解释

Dimensionality reduction along one axis of a form.

Compresses one axis of a 2D form into a small number of components.
The other axis becomes the observation axis of the output.

Two kinds of input
------------------
1. Feature matrix ``[feature, sample]`` (or the reverse). The
operator compresses the feature axis into components. Methods:
``pca``, ``umap``, ``tsne``.

2. Square distance matrix ``[sample, sample_b]`` (produced by
``distance_matrix``). The operator computes principal coordinates
of the distance matrix. Method: ``pcoa``.

The output always has the form::

dims = [<observation_dim>, "component"]

Output component labels
-----------------------
pca   -> "PC1", "PC2", ...
pcoa  -> "PCo1", "PCo2", ...
umap  -> "UMAP1", "UMAP2", ...
tsne  -> "tSNE1", "tSNE2", ...

Standardization
---------------
For ``pca`` / ``umap`` / ``tsne``, ``standardize=True`` (default)
divides each fea

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_microbiome.py |
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
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^reduce,' verification/coverage-8.0.1/operator_coverage.csv
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
