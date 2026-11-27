# T05 · 乳腺癌复发与肺腺癌的差异表达：真实 GEO 复现

## 科学问题
GSE2034 与 GSE10072 上差异表达、通路富集与生存关联能否复现原文？批次校正会改变多少结论？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| GEO GSE2034 | matrix | 5 MB | GEO public | https://ftp.ncbi.nlm.nih.gov/geo/series/GSE2nnn/GSE2034/matrix/GSE2034_series_matrix.txt.gz |
| GEO GSE10072 | matrix | 10 MB | GEO public | https://ftp.ncbi.nlm.nih.gov/geo/series/GSE10nnn/GSE10072/matrix/GSE10072_series_matrix.txt.gz |
| MSigDB Hallmark | GMT | 180 KB | CC BY 4.0 | https://data.broadinstitute.org/gsea-msigdb/msigdb/release/2024.1.Hs/h.all.v2024.1.Hs.symbols.gmt |

引用：
- GEO GSE2034: Wang 2005
- GEO GSE10072: Landi 2008
- MSigDB Hallmark: Liberzon 2015

## 分析路线
1. TsvReader 读矩阵/GMT
2. log_transform/quantile_normalize/filter
3. pca_transform/sample_clustering/heatmap
4. differential_expression/multiple_testing_correction
5. gsea_enrichment/over_representation
6. kaplan_meier_plot/cox_regression
7. descriptive_stats/normality/effect_size

## 交付
图：
- PCA 与聚类
- 火山图与 top50 热图
- GSEA 富集
- KM 与 Cox 森林图

表：
- DE top 表
- 富集通路表
- Cox 系数表

论文支撑：Methods（队列/预处理/统计）· Results（DE/富集/生存）· Discussion（复现性与批次效应）

## 覆盖（副产物）
本任务预计调用算子 50 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
