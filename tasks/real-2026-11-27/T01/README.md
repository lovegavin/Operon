# T01 · IL-7Rα 的 de novo minibinder：设计-验证闭环

## 科学问题
针对 IL-7Rα（PDB 3DI3 链 B）设计 58 aa α 螺旋 minibinder，并用计算证据决定哪些候选值得合成；同时回答：常见 RFdiffusion+ProteinMPNN 配方里哪些失败是几何/坐标造成的、哪些是序列退化造成的。

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| RCSB 3DI3 | mmCIF | 313 KB | PDB CC0 | https://files.rcsb.org/download/3DI3.cif |
| UniProt P16871 | FASTA | 1 KB | CC BY 4.0 | https://rest.uniprot.org/uniprotkb/P16871.fasta |

引用：
- RCSB 3DI3: RCSB PDB
- UniProt P16871: UniProt

## 分析路线
1. MmcifReader 读 3DI3
2. structure_extract_chain 取链 B（校验坐标离散度）
3. rfdiffusion_design contig B21-213/0 58，4 设计
4. proteinmpnn_design 每设计 2 序列
5. colabfold_predict 单序列 + 真实 MSA 两条件
6. protein_properties / protein_instability / 界面指标
7. structure_openmm_md_stability 5000 步
8. export_results 导出

## 交付
图：
- 设计几何：binder-靶标最小距离、Rg、端到端距离（修复前后）
- 序列复杂度与 MPNN score
- pLDDT×界面×instability 排序散点
- MD RMSD/Rg 轨迹

表：
- 候选表（design/seq、min-distance、Rg、pLDDT、界面、GRAVY、instability）
- 缺陷对照表（坐标坍缩/MPNN 退化/单序列 vs MSA）

论文支撑：Methods（配方与判废阈值）· Results（几何-序列-置信度三层筛选）· Discussion（单链 pLDDT 的局限）

## 覆盖（副产物）
本任务预计调用算子 52 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
