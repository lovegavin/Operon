# GLP-1R-ACTIVATE-VHH · de novo VHH-style binder for GLP-1R：跨靶标可迁移性

## 科学问题
同一设计配方换到 GLP-1R（PDB 6X18 链 F）是否成立？几何校验与序列质量阈值是通用规则还是靶标特异？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| RCSB 6X18 | mmCIF | 1.2 MB | PDB CC0 | https://files.rcsb.org/download/6X18.cif |
| UniProt P43220 | FASTA | 1 KB | CC BY 4.0 | https://rest.uniprot.org/uniprotkb/P43220.fasta |

引用：
- RCSB 6X18: RCSB PDB
- UniProt P43220: UniProt

## 分析路线
1. 读 6X18 取链 F（P43220 38-138）
2. rfdiffusion_design F38-138/0 58，4 设计
3. proteinmpnn_design 2 序列/设计
4. colabfold_predict 单序列
5. 界面/理化/MD(top1)
6. 跨靶标统计

## 交付
图：
- 两靶标几何对比
- 两靶标序列复杂度对比
- 两靶标 pLDDT/界面散点

表：
- 跨靶标候选表
- 配方参数对照表

论文支撑：Methods（同配方）· Results（一致性）· Discussion（可迁移性）

## 覆盖（副产物）
本任务预计调用算子 0 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
