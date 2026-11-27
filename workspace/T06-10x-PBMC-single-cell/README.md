# T06 · 10x PBMC 单细胞图谱：分群、标记与轨迹

## 科学问题
10x PBMC 4k 上标准 QC-降维-聚类能否复现经典免疫分群？标记基因是否与 CellMarker 一致？轨迹是否重现单核/淋巴连续性？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| 10x PBMC 4k h5 | h5 | 30 MB | 10x public | https://cf.10xgenomics.com/samples/cell-exp/2.1.0/pbmc4k/pbmc4k_filtered_gene_bc_matrices_h5.h5 |
| CellMarker 2.0 | xlsx | 2 MB | academic use | http://117.50.127.228/CellMarker/CellMarker_download_files/file/Cell_marker_Human.xlsx |

引用：
- 10x PBMC 4k h5: Zheng 2017
- CellMarker 2.0: Hu 2023

## 分析路线
1. H5adReader/TenxH5Reader
2. cell_qc_metrics/doublet_detection/filter_cells
3. normalize/highly_variable_genes
4. pca/umap_embedding
5. graph_clustering/leiden
6. marker_gene_detection/cell_type_annotation
7. trajectory/pseudotime

## 交付
图：
- QC 小提琴与双细胞得分
- UMAP 与 marker 点图
- 细胞比例与 marker 热图
- 伪时间轨迹

表：
- 分群统计表
- QC 汇总

论文支撑：Methods（10x/QC/聚类）· Results（分群/marker/轨迹）· Discussion（文献对照）

## 覆盖（副产物）
本任务预计调用算子 26 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
