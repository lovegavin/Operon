# 森林图（forest_plot）

把一张“每行一个协变量、每行 HR 与置信区间”的表画成森林图（forest plot），**直接产出图片文件**，不返回 Form 表。

## Inputs

| 名称 | 类型/维度 | 必填 | 说明 |
| --- | --- | --- | --- |
| `inputs[0]` | 2-D numeric Form，dims 为 `dim` × `stat_dim`（默认 `covariate` × `statistic`） | 是 | 唯一输入端口（`inputs_arity = 1`）。`dim` 维给出协变量名（每行一个），`stat_dim` 维是统计量列；四个统计量列（HR、CI 下界、CI 上界、可选 P）按**列名标签**在 `stat_dim` 上查找，找不到就报错。 |

典型上游是 Cox 回归结果表：一行一个协变量，列名包含 `HR`、`CI_low`、`CI_high`（以及可选的 `P`）。列名不同则必须用 `hr_label` / `low_label` / `high_label` / `p_label` 指定。

## Outputs

| 名称 | 类型/维度 | 说明 |
| --- | --- | --- |
| 无 Form 输出 | — | 该算子 `output.mode = "none"`、`outputs` 为空、`output_parameter` 为 `None`：**没有可连线的端口**，下游节点无法把它当表格读。 |
| 图片文件（副作用） | PNG / PDF / SVG 等 | 写到当前运行目录的 `figures/` 子目录下，文件名由 `filename` 决定；同一次运行还会**额外**写出同名的 `.png`、`.pdf`、`.svg` 三份（请求的格式 + 这两种矢量格式，去重后合并），并写一个 `<stem>.figure.json` 清单记录每份图片的 id、格式、路径、物理尺寸（mm）与 dpi。 |

返回给运行报告的是一份图片清单（`figure_report`），含 `filename`、`path`、`figures[]` 以及本次的 `n_total` / `n_valid` / `n_significant` / `n_ns` 和逐行 `{covariate, HR, CI_low, CI_high, P, significant}`。文件名冲突时自动加 `-2`、`-3` 后缀，不会覆盖旧图。

## Parameters

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `dim` | string | `covariate` | 协变量所在维度名（行维）。 |
| `stat_dim` | string | `statistic` | 统计量所在维度名（列维）；HR/CI/P 的列名标签在这一维上查找。 |
| `hr_label` | string | `HR` | 效应量（hazard ratio）列名。 |
| `low_label` | string | `CI_low` | 置信区间下界列名。 |
| `high_label` | string | `CI_high` | 置信区间上界列名。 |
| `p_label` | string | `P` | p 值列名；该列不存在时按“无 P 值”处理，显著性改由区间是否跨 1 判定。 |
| `filename` | string | — | **必填**，输出图片文件名（如 `forest_plot.png`）。必须是图片/PDF 后缀且落在 `figures/` 目录内。 |
| `title` | string | — | 图标题；不给则无标题。 |
| `xlabel` | string | `Hazard ratio (95% CI)` | x 轴标题。 |
| `xlim` | array（2 个数字） | — | x 轴范围，必须是 `[min, max]` 形式的**列表**且 `min < max`；给对象或其他形式会报错。 |
| `color_sig` | string | `#D62728` | 显著行（区间不跨 1 或 `P < 0.05`）的颜色。 |
| `color_ns` | string | `#4C72B0` | 不显著行的颜色。 |
| `sort_by` | enum | `input` | 行排序：`input` 保持输入顺序，`hr` 按 HR 升序，`p` 按 P 升序（P 缺失/非有限按 1.0 参与排序）。 |
| `log_scale` | boolean | `true` | x 轴是否取对数；开启时要求 HR 与 CI 均为正（非正行会被过滤掉）。 |
| `figure_width_mm` | number | — | 物理宽度（毫米）；给出时按比例缩放高度，未给出则宽度上限 180 mm。 |
| `figure_height_mm` | number | — | 物理高度（毫米），覆盖按比例算出的高度。 |
| `figure_dpi` | integer | `300` | 位图 dpi（PNG 与栅格化图层）；PDF/SVG 的文字与坐标轴仍是矢量。 |
| `figure_font_size` | number | `8` | 图内字号（pt）。 |

## Notes

- **这是“画图节点”，不是“数据节点”**：没有 Form 输出，不能接在需要表格的下游之前；需要数值结果时请另接统计算子，森林图只负责可视化。
- 行过滤：只有 `HR`、`CI_low`、`CI_high` 全部有限、且两个区间端点都 `> 0` 的行才会被画出来（对数轴的要求）。**代码不校验 `CI_low <= CI_high`**，端点写反会画出反向误差棒而不报错。
- 全部行被过滤时抛 `StepError("forest_plot: no rows with finite HR and CI")`，不会产出空白图。
- 显著性：有 `P` 列时按 `P < 0.05`；没有 `P` 列时按区间是否完全在 1 的同一侧。参考线固定在 HR = 1（虚线）。
- `filename` 会被解析到 `<运行目录>/figures/` 之下：写到该目录之外、或用不在 `{.png,.pdf,.svg,.jpg,.jpeg,.tif,.tiff,.webp}` 内的后缀，都会抛 `ValueError("Figure filename must be an image/PDF inside the figures directory")`。
- 依赖 matplotlib：算子的 `resources` 里没有声明 `dependencies`，但运行时会 `import matplotlib.pyplot`，共享解释器缺少 matplotlib 会直接失败。
- 图尺寸默认约 5.5 英寸宽、高度随行数 `0.35 * n + 1.5` 增长（最小 2.5 英寸）；行数很多时图会变得很长，建议配合 `figure_height_mm` 或先筛行。
