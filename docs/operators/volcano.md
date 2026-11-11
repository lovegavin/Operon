# Volcano (`volcano`)

**Category:** 可视化  
**Entry point:** `src.task.step.steps.volcano:VolcanoStep`  
**Source:** [`library/seed/src/task/step/steps/volcano.py`](../../library/seed/src/task/step/steps/volcano.py) (278 lines)  
**Trust level: C — 专用测试引用 + 可编译路线**

## 1. 代码说明

效应大小与显著性

> Volcano plot of a differential comparison result. Input is a 2D form with a feature dim and a "statistic" dim that carries the columns log2FC, P, and optionally Q_VALUE. Points are classified by both thresholds: up log2FC > lfc_threshold and P < p_threshold down log2FC < -lfc_threshold and P < p_threshold ns everything else Missing or non-finite rows are skipped. Params: dim : feature dim (default "gene") stat_dim : statistic dim (default "statistic") lfc_label : column label for log2FC (default "log2FC") p_label : column label for P (default "P") lfc_threshold : |log2FC| cutoff (default 1.0)…

关键符号：

- `class VolcanoStep (line 42)`

协议：v3 / revision `3.7`；输出参数 `None`。

### 输入与输出

- 输入 1: ndim=2, numeric=True, dims=(dim, stat_dim), info=(—)
- 输出: mode=none, schema={}

### 参数

| 参数 | 默认值 | 含义/约束 |
| --- | --- | --- |
| `dim` | `gene` | 分析维度 |
| `stat_dim` | `statistic` | 统计量维度 |
| `lfc_label` | `log2FC` | log2FC 字段 |
| `p_label` | `P` | P / Q 字段 |
| `filename` | `` | 图片文件名 |
| `title` | `` | 图标题 |
| `xlabel` | `` | X 轴标题 |
| `ylabel` | `-log10(P)` | Y 轴标题 |
| `lfc_threshold` | `1.0` | log2FC 阈值 |
| `p_threshold` | `0.05` | 显著性阈值; min 0; max 1 |
| `point_size` | `8` | 点大小; min 1 |
| `alpha` | `0.7` | 透明度; min 0; max 1 |
| `label_top` | `0` | 标记前 N 个特征; min 0 |
| `figure_width_mm` | `` | Figure width (mm) |
| `figure_height_mm` | `` | Figure height (mm) |
| `figure_dpi` | `300` | Figure resolution (DPI); min 72 |
| `figure_font_size` | `8` | Figure font size (pt) |

## 2. 用途与解释

Volcano plot of a differential comparison result.

Input is a 2D form with a feature dim and a "statistic" dim that
carries the columns log2FC, P, and optionally Q_VALUE.

Points are classified by both thresholds:

up       log2FC >  lfc_threshold and P < p_threshold
down     log2FC < -lfc_threshold and P < p_threshold
ns       everything else

Missing or non-finite rows are skipped.

Params:
dim           : feature dim (default "gene")
stat_dim      : statistic dim (default "statistic")
lfc_label     : column label for log2FC (default "log2FC")
p_label       : column label for P (default "P")
lfc_threshold : |log2FC| cutoff (default 1.0)
p_threshold   : P cutoff (default 0.05)
filename      : output file name (required)
title         : optional plot title
xlabel        : optional x label (default: lfc_label)
ylabel        : optional y label (default: "-log10(P)")
point_size    : marker 

## 3. 正确性依据

**结论：C 级。** 路线已编译进 79 条内置路线，并有专用测试引用；没有记录为本算子单独执行过真实数据。

| 层 | 状态 | 证据 |
| --- | --- | --- |
| L1 契约/清单 | PASS | verification/operator-audit-8.0.1/operator_table.csv |
| L2 单元/oracle | UNIT | tests/test_figure_contract.py,test_plot_examples.py,test_report_contracts_sop.py,test_upstream_operators.py |
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
grep '^volcano,' verification/coverage-8.0.1/operator_coverage.csv
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
