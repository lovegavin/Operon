# 归一化 (`normalize`)

**Category:** 数据整理  
**Entry point:** `src.task.step.steps.normalize:NormalizeStep`  
**Source:** [`library/seed/src/task/step/steps/normalize.py`](../../library/seed/src/task/step/steps/normalize.py) (377 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

CPM、DESeq2 size factors、Quantile 或

> Normalize a Form along one dimension. Applies a sample-level normalization. Standard second step after filtering, for any count or intensity matrix (RNA-seq, proteomics, metabolomics, single-cell). Supported methods ----------------- cpm counts per million: divide each sample by its total, then scale to ``target_sum`` total divide each sample by its total (sum = 1) median_of_ratios DESeq2 size factors: per-gene geometric mean, per-sample median of ratios quantile quantile normalization: for each rank position, replace the value with the mean of that rank across all samples zscore z-score each…

关键符号：

- `class NormalizeStep (line 52)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=?, numeric=True, dims=(dim), info=(—)
- 输出: mode=transform, schema={}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `method` | `` | 方法; choices: cpm, total, median_of_ratios, quantile, zscore |
| `dim` | `` | 分析维度 |
| `target_sum` | `1000000.0` | 目标总量; min 0 |

## 2. 用途与解释

Transform numeric values using a declared normalization method while preserving
dimension names and labels. Choose the method from assay assumptions; these
methods are not interchangeable measures of biological abundance.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_core_operators_sop.py,test_execution_service.py,test_extension2_operators.py,test_import_autolocate.py,test_internal_params.py,test_protocol_v2.py,test_r_oracles.py,test_studio_import_root.py,test_task_tools.py,test_upstream_operators.py |
| L3 真实执行 | ROUTE | operator_table.csv:builtin_route |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。
- 注意：该算子没有独立数值 oracle， correctness 仅到“契约/测试/执行”层级。

## 4. 限制与失败模式

The implementation declares full-memory execution. Missing entries are handled
according to the input convention and propagated as NaN. Zero totals, constant
samples and distributional differences require careful interpretation. No method
here automatically establishes that batch effects or confounding have been removed.

## 5. 复现

```bash
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^normalize,' verification/coverage-8.0.1/operator_coverage.csv
```

算子手册中的示例：

```text
`examples/documented_operators/run_example.py` provides a tested synthetic CSV ->
zscore -> PCA example. Its method is chosen to demonstrate the interface; use an
assay-appropriate alternative for scientific data.
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
