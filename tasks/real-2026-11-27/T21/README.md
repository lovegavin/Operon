# T21 · 真实表格数据上的机器学习基准

## 科学问题
在真实公开表格数据（UCI Adult、Wine、MNIST 子集）上，分类/回归/聚类/降维/异常检测的多种实现能否给出可复现的基准排序？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| UCI Adult | CSV | 4 MB | CC BY 4.0 | https://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.data |
| UCI Wine | CSV | 20 KB | CC BY 4.0 | https://archive.ics.uci.edu/ml/machine-learning-databases/wine/wine.data |

引用：
- UCI Adult: Dua 2019
- UCI Wine: Dua 2019

## 分析路线
1. TsvReader/CsvReader
2. train_test_split/feature_scaling
3. 分类器（RF/GBM/SVM/KNN/AdaBoost/朴素贝叶斯…）
4. 回归器（线性/岭/Lasso/树集成）
5. 聚类（KMeans/层次/DBSCAN/BIRCH）
6. 降维（PCA/t-SNE/UMAP）
7. 异常检测（IForest/LOF/自编码器）
8. 指标（AUC/F1/ARI/轮廓）

## 交付
图：
- 模型准确率/耗时对比
- ROC/PR 曲线
- 聚类轮廓与 ARI
- 降维可视化

表：
- 基准结果表
- 超参数与复现命令

论文支撑：Methods（数据/模型/交叉验证）· Results（排序）· Discussion（偏差与稳健性）

## 覆盖（副产物）
本任务预计调用算子 69 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
