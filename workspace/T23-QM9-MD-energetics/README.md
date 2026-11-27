# T23 · 量子化学与分子动力学：真实 QM9 与蛋白配体能量

## 科学问题
真实 QM9 分子上，DFT 单点能/几何优化与描述符能否复现参考能量？蛋白-配体复合物的自由能计算误差量级如何？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| QM9 | CSV | 20 MB | CC0 | https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/qm9.csv |
| PDB 1IEP | PDB | 435 KB | PDB CC0 | https://files.rcsb.org/download/1IEP.pdb |

引用：
- QM9: Ramakrishnan 2014
- PDB 1IEP: Nagar 2002

## 分析路线
1. 读 QM9/复合物
2. quantum_chem/dft 单点与优化
3. 分子描述符/轨道能级
4. MM/自由能计算
5. 误差统计

## 交付
图：
- 能量误差分布
- 轨道能级与描述符相关
- 自由能收敛

表：
- QM 结果表
- 自由能汇总

论文支撑：Methods（方法/基组/力场）· Results（误差）· Discussion（适用边界）

## 覆盖（副产物）
本任务预计调用算子 3 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
