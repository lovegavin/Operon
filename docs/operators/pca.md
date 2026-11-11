# PCA (`pca`)

**Category:** 统计分析  
**Entry point:** `src.task.step.steps.pca:PcaStep`  
**Source:** [`library/seed/src/task/step/steps/pca.py`](../../library/seed/src/task/step/steps/pca.py) (161 lines)  
**Trust level: A- — 独立 oracle（未记录真实执行）**

## 1. 代码说明

标准化数据，提取主成分；缺失值以特征均值填充。

> Principal component analysis. Compresses one dimension of a 2D form into a small number of principal components. The other dimension becomes the "observation" axis of the output. Missing cells are filled with the column mean before standardization. The output retains observation annotations and declares score semantics. Layout: input : [<dim_to_compress>, <observation_dim>] (any 2D orientation) output : [<observation_dim>,

关键符号：

- `class PcaStep (line 26)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(dim), info=(missing_code)
- 输出: mode=pca, schema={}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `dim` | `` | 压缩维度 |
| `n_components` | `10` | 主成分数量; min 1 |

## 2. 用途与解释

Summarize variation in a two-dimensional numeric matrix using principal component
scores. Use this to inspect sample relationships and potential outliers; a visual
separation alone does not establish a biological mechanism or statistical result.

## 3. 正确性依据

**结论：A- 级。** 独立实现「numpy SVD on transposed, standardized matrix」。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | ORACLE | operator_table.csv:l2_oracle |
| L3 真实执行 | ROUTE | operator_table.csv:builtin_route |
| L4 资源 | MEASURED | operator_table.csv:deterministic |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

独立 oracle 细节：

- 参考实现：numpy SVD on transposed, standardized matrix
- 结果：pass=True, delta=None, tolerance=None

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。

## 4. 限制与失败模式

The current implementation uses a full dense SVD and declares full-memory
execution. Disk-backed input does not make the SVD itself streaming. Scaling gives
features comparable variance, which may amplify low-information features. Apply
assay-appropriate filtering and transformation before interpreting the plot.

## 5. 复现

```bash
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^pca,' verification/coverage-8.0.1/operator_coverage.csv
```

算子手册中的示例：

```text
The executable synthetic example is `examples/documented_operators/run_example.py`.
Run `python -m examples.documented_operators.run_example ./example-output` from the
repository root. It checks a compressed CSV -> normalize -> PCA pipeline and
preserves sample labels. Its input is synthetic, not an analysis recommendation.
```

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
