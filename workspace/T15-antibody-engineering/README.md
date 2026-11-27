# T15 · 抗体工程：真实 IgG 结构的 CDR 编号、可开发性与再设计

## 科学问题
在真实抗体结构（1HZH、SAbDab 片段）上，KabIGT/IMGT 编号、CDR 物化性质与可开发性评分能否复现文献排序？CDR 重设计会破坏框架吗？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| PDB 1HZH | PDB | 1.1 MB | PDB CC0 | https://files.rcsb.org/download/1HZH.pdb |
| SAbDab summary | CSV | 20 MB | academic | https://opig.stats.ox.ac.uk/webapps/newsabdab/sabdab/summary/all |

引用：
- PDB 1HZH: Saphire 2001
- SAbDab summary: Dunbar 2014

## 分析路线
1. 读抗体结构/序列
2. antibody_numbering_kabat/imgu
3. CDR 长度/物化/亲水性
4. antibody_developability
5. antibody_cdr_redesign/graft
6. 与文献排序比较

## 交付
图：
- CDR 长度分布
- 可开发性评分排序
- 重设计前后序列/结构差异

表：
- 抗体表（编号/长度/评分）
- 重设计候选表

论文支撑：Methods（编号方案/评分）· Results（CDR/可开发性）· Discussion（再设计风险）

## 覆盖（副产物）
本任务预计调用算子 11 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
