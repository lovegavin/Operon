# Gaussian image blur (`image_gaussian_blur`)

**Category:** Imaging  
**Entry point:** `src.task.step.steps.image_gaussian_blur:ImageGaussianBlurStep`  
**Source:** [`library/seed/src/task/step/steps/image_gaussian_blur.py`](../../library/seed/src/task/step/steps/image_gaussian_blur.py) (34 lines)  
**Trust level: A- — 独立 oracle（未记录真实执行）**

## 1. 代码说明

Separable Gaussian blur with reflect padding for 2D image

> Gaussian image blur

关键符号：

- `class ImageGaussianBlurStep (line 12)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(row_dim, field_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `output` | `image_gaussian_blur_out` | — |
| `row_dim` | `row` | — |
| `field_dim` | `field` | — |
| `sigma` | `1.5` | — |
| `truncate` | `4.0` | — |

## 2. 用途与解释

Implements `image_gaussian_blur` for image-like numeric tables. The operator
builds a one-dimensional Gaussian kernel from `sigma` and `truncate`, applies it
along both axes with symmetric edge padding, and returns the filtered matrix
preserving the input labels and shape.

## 3. 正确性依据

**结论：A- 级。** 独立实现「scipy.ndimage.gaussian_filter」，实测差值 4.995e-10。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | ORACLE | operator_table.csv:l2_oracle |
| L3 真实执行 | ROUTE | operator_table.csv:generated_route |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

独立 oracle 细节：

- 参考实现：scipy.ndimage.gaussian_filter
- 结果：pass=True, delta=4.995169000654442e-10, tolerance=None

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。

## 4. 限制与失败模式

Only two-dimensional numeric tables are supported (CSV/TSV export is 2-D only).
Edges use symmetric padding (the edge sample is repeated), which matches
`scipy.ndimage.gaussian_filter` with `mode="reflect"` for the tested range but is
not a full boundary-condition model.

## 5. 复现

```bash
cd /home/gavin/Operon-7015-native
python -m operon registry check --json
grep '^image_gaussian_blur,' verification/coverage-8.0.1/operator_coverage.csv
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
