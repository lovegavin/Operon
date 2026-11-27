# T10 · 真实 TMT 蛋白质组：谱图质控与鉴定率

## 科学问题
PRIDE PXD000001 上谱图预处理、峰识别与鉴定率能否复现原文 QC 指标？哪类谱图最易失败？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| PXD000001 mzXML | mzXML | 200 MB | CC0 | https://ftp.pride.ebi.ac.uk/pride/data/archive/2012/03/PXD000001/TMT_Erwinia_1uLSike_Top10HCD_isol2_45stepped_60min_01.mzXML |
| UniProt Erwinia | FASTA | 2 MB | CC BY 4.0 | https://rest.uniprot.org/uniprotkb/stream?query=organism_id:465817&format=fasta |

引用：
- PXD000001 mzXML: PXD000001
- UniProt Erwinia: UniProt

## 分析路线
1. MzxmlReader
2. spectrum_qc/peak_detection/precursor
3. peptide_identification/fdr
4. quantification/protein_rollup
5. 统计与图

## 交付
图：
- TIC/峰数/质量误差
- 鉴定率与 FDR
- TMT reporter 分布

表：
- 谱图 QC 表
- 鉴定/定量汇总

论文支撑：Methods（数据/预处理/FDR）· Results（QC/鉴定率）· Discussion（对照）

## 覆盖（副产物）
本任务预计调用算子 19 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
