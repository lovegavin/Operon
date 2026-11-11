# Median-normalize an LFQ matrix (`lfq_median_normalize`)

**Category:** Proteomics  
**Entry point:** `src.task.step.steps.lfq_median_normalize:LfqMedianNormalizeStep`  
**Source:** [`library/seed/src/task/step/steps/lfq_median_normalize.py`](../../library/seed/src/task/step/steps/lfq_median_normalize.py) (80 lines)
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

Divide each sample column by its median and rescale to the global median of

关键符号：

- `class LfqMedianNormalizeStep (line 11)`

协议：v3 / revision `3.7`；输出参数 `output`。

### 输入与输出

- 输入 1: ndim=?, numeric=True, dims=(protein_dim, sample_dim), info=(—)
- 输出: mode=declare, schema={"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `protein_dim` | `protein` | Protein dim |
| `sample_dim` | `sample` | Sample dim |
| `output` | `normalized` | Output |

## 2. 用途与解释

Median normalization removes sample loading differences by scaling
each sample so that its median peptide intensity matches a common target.

The operator accepts a 2D protein x sample matrix. Non-finite and
non-positive entries are treated as missing and stay missing after scaling.
Per-sample medians and scaling factors are reported in `info`.

Limitations: median normalization assumes most proteins are unchanged and
does not impute missing values; it is not a replacement for intensity-based
absolute quantification.

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_lfq_panel_b67.py |
| L3 真实执行 | ROUTE | operator_table.csv:generated_route |
| L4 资源 | ESTIMATE | definition resources.estimate=estimate_memory |
| L5 应用安装 | INSTALL | 8.0.1 bundle install (3.1.9/4.0.0) |

### 这个证据证明什么、不证明什么

- 证明：契约可解析、输入输出维度一致；有执行记录时，真实数据能跑到 `Task finished` 并产生可校验产物。
- 不证明：该算子在该数据集上的生物学结论正确；统计假设是否成立仍需使用者判断。
- 注意：该算子没有独立数值 oracle， correctness 仅到“契约/测试/执行”层级。

## 4. 限制与失败模式

相邻算子 Markdown 是参数约束与失败模式的权威说明；未找到单独的限制段。

## 5. 复现

```bash
cd /path/to/Operon-worktree
python -m operon registry check --json
grep '^lfq_median_normalize,' verification/coverage-8.0.1/operator_coverage.csv
```

未补齐证据：`L4_MEASURED`。

---

由 `scripts/build_operator_trust_docs.py` 生成；审计基线 8.0.1。
