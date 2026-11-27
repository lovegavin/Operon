# T09 · MicrobiomeHD：跨研究肠道菌群复现

## 科学问题
MicrobiomeHD 多队列上 α/β 多样性与差异丰度能否复现各研究疾病信号？异质性与效应量一致性如何？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| MicrobiomeHD | zip/TSV | 20 MB | MIT | https://raw.githubusercontent.com/cduvallet/microbiomeHD/master/data.zip |

引用：
- MicrobiomeHD: Duvallet 2017

## 分析路线
1. BiomReader/TsvReader
2. alpha_diversity/rarefaction
3. beta_diversity/pcoa/permanova
4. differential_abundance/lefse/ancom
5. taxonomic_profiling

## 交付
图：
- α 多样性与稀释曲线
- PCoA
- 差异丰度森林图
- 跨研究一致性

表：
- 研究汇总表
- 显著分类单元表

论文支撑：Methods（队列/多样性/DA）· Results（多样性/群落）· Discussion（异质性）

## 覆盖（副产物）
本任务预计调用算子 30 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
