# T25 · 空间转录组与多组学：真实 10x Visium

## 科学问题
真实 Visium 数据上，空间聚类、区域标记与配体-受体共定位能否重建组织区域结构？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| 10x Visium 样本 | h5 | 200 MB | 10x public | https://cf.10xgenomics.com/samples/spatial-exp/2.0.0/Visium_Human_Breast_Cancer/Visium_Human_Breast_Cancer_filtered_feature_bc_matrix.h5 |

引用：
- 10x Visium 样本: 10x Genomics

## 分析路线
1. VisiumReader
2. spatial_qc/normalize
3. spatial_clustering/neighborhood
4. region_markers
5. ligand_receptor

## 交付
图：
- 空间聚类图
- 区域 marker 热图
- 共定位网络

表：
- 区域统计表
- marker 表

论文支撑：Methods（Visium/聚类）· Results（区域/互作）· Discussion（分辨率）

## 覆盖（副产物）
本任务预计调用算子 4 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
