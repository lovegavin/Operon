# T11 · ABL 激酶虚拟筛选：ZINC 到对接

## 科学问题
以 1IEP（含伊马替尼）为靶点，从 ZINC 分子库出发，描述符/指纹筛选与对接能否把已知抑制剂排在合理分位？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| PDB 1IEP | PDB | 435 KB | PDB CC0 | https://files.rcsb.org/download/1IEP.pdb |
| ZINC250k | SMILES | 20 MB | ZINC academic | https://raw.githubusercontent.com/aspuru-guzik-group/chemical_vae/master/models/zinc/250k_rndm_zinc_drugs_clean_5.txt |
| RDKit 5k | SMILES | 190 KB | BSD-3 | https://raw.githubusercontent.com/rdkit/rdkit/master/Data/NCI/first_5K.smi |

引用：
- PDB 1IEP: Nagar 2002
- ZINC250k: Irwin 2005
- RDKit 5k: RDKit

## 分析路线
1. SmiReader
2. molecule_standardization/protonation
3. descriptors/morgan_fingerprint
4. similarity/clustering/scaffold
5. lipinski/admet
6. protein_ligand_docking
7. 统计与排序

## 交付
图：
- 描述符与 RO5 通过率
- 相似性/骨架聚类
- 对接打分分布

表：
- 类药性表
- 对接 top 命中

论文支撑：Methods（分子库/描述符/对接）· Results（类药性/多样性/对接）· Discussion（局限）

## 覆盖（副产物）
本任务预计调用算子 35 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
