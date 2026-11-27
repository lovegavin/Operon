# T08 · GM12878 Hi-C：A/B 区室与 TAD

## 科学问题
Rao 2014 GM12878 上 A/B 区室与 TAD 边界能否与已发表分区一致？绝缘分数与 cCRE 重叠是否支持边界功能？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| 4DN GM12878 mcool | mcool | 1-2 GB | 4DN CC BY 4.0 | https://data.4dnucleome.org/files-processed/4DNFI1UEG1RT/@@download/4DNFI1UEG1RT.mcool |

引用：
- 4DN GM12878 mcool: Rao 2014

## 分析路线
1. CoolerReader chr21 100kb
2. matrix_balancing/matrix_stats
3. compartment_analysis/eigenvector
4. tad_detection/insulation/boundary
5. bed_interval_operations

## 交付
图：
- 原始 vs 平衡化矩阵
- PC1 区室轨道
- TAD 与绝缘分数
- 边界-cCRE 富集

表：
- 矩阵统计表
- TAD 汇总表

论文支撑：Methods（数据/分辨率/算法）· Results（区室/TAD）· Discussion（敏感性）

## 覆盖（副产物）
本任务预计调用算子 16 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
