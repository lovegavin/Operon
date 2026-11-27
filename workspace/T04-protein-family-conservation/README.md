# T04 · 球蛋白与 GPCR 家族的保守性与选择压力

## 科学问题
在 Pfam 真实种子比对（PF00042、PF00001）上，比对/建树能否稳定重建系统发育、识别正选择位点并映射回真实三维结构？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| Pfam PF00042 seed | Stockholm | 8 KB | Pfam CC0 | https://www.ebi.ac.uk/interpro/wwwapi/entry/pfam/PF00042/?annotation=alignment:seed&download |
| Pfam PF00001 seed | Stockholm | 1 MB | Pfam CC0 | https://www.ebi.ac.uk/interpro/wwwapi/entry/pfam/PF00001/?annotation=alignment:seed&download |
| PDB 1UBQ | PDB | 80 KB | PDB CC0 | https://files.rcsb.org/download/1UBQ.pdb |

引用：
- Pfam PF00042 seed: Mistry 2021
- Pfam PF00001 seed: Mistry 2021
- PDB 1UBQ: Vijay-Kumar 1987

## 分析路线
1. StockholmReader 读种子比对
2. alignment_stats/conservation/consensus
3. distance_matrix + neighbor_joining_tree
4. tree_compare/tree_rooting
5. motif_discovery/selection_pressure
6. 保守位点映射到结构

## 交付
图：
- 比对覆盖度与保守性曲线
- 系统发育树与支持度
- 正选择/保守位点结构映射

表：
- 家族统计表
- dN/dS 位点表

论文支撑：Methods（Pfam、建树、dN/dS）· Results（保守性/树/位点）· Discussion（注释可复现性）

## 覆盖（副产物）
本任务预计调用算子 47 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
