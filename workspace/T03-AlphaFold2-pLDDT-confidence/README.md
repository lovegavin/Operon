# T03 · AlphaFold2 置信度到底能信多少：pLDDT 与实验结构

## 科学问题
AF2/ColabFold 的 pLDDT 与实验结构（1UBQ、1L2Y、3DI3）偏差多大？单序列与 MSA 两种模式是否改变结论？隐式溶剂 MD 能否重现实验 B-factor 高的柔性区？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| PDB 1UBQ | PDB | 80 KB | PDB CC0 | https://files.rcsb.org/download/1UBQ.pdb |
| PDB 1L2Y | PDB | 960 KB | PDB CC0 | https://files.rcsb.org/download/1L2Y.pdb |
| PDB 3DI3 | mmCIF | 313 KB | PDB CC0 | https://files.rcsb.org/download/3DI3.cif |

引用：
- PDB 1UBQ: Vijay-Kumar 1987
- PDB 1L2Y: Neidigh 2002
- PDB 3DI3: RCSB

## 分析路线
1. 读三个实验结构
2. colabfold_predict(single_sequence 与 msa_host)
3. superpose/RMSD/TM-score 与实验比较
4. pLDDT/PAE 与 B-factor 对照
5. MD stability+rmsf
6. 统计：相关与误差分布

## 交付
图：
- 逐残基 pLDDT vs B-factor
- 预测-实验叠合与 RMSD/TM
- 单序列 vs MSA
- MD RMSD/Rg/RMSF

表：
- 结构基准表（RMSD/TM/pLDDT/PAE）
- MD 与柔性残基表

论文支撑：Methods（预测/评估/MD）· Results（置信度-精度）· Discussion（pLDDT 不是结合判据）

## 覆盖（副产物）
本任务预计调用算子 28 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
