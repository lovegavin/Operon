# T13 · GENCODE vs RefSeq：真实注释一致性

## 科学问题
chr22 上两套权威注释的基因/转录本/外显子结构与 UTR 统计是否一致？区间运算如何量化差异来源？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| GENCODE v49 GTF | GTF | 50 MB | GENCODE open | https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_49/gencode.v49.annotation.gtf.gz |
| RefSeq GFF3 | GFF3 | 90 MB | NCBI public domain | https://ftp.ncbi.nlm.nih.gov/refseq/H_sapiens/annotation/GRCh38_latest_genomic.gff.gz |
| GO basic OBO | OBO | 35 MB | CC BY 4.0 | https://release.geneontology.org/2024-11-01/ontology/go-basic.obo |

引用：
- GENCODE v49 GTF: Frankish 2019
- RefSeq GFF3: O'Leary 2016
- GO basic OBO: GO Consortium

## 分析路线
1. GtfReader/GffReader/OboReader
2. interval_merge/overlap
3. gene_structure_stats/exon_intron/utr
4. annotation_compare
5. go_enrichment

## 交付
图：
- 基因/转录本/外显子数量对照
- 外显子数与 UTR 长度分布
- 重叠/独有区间

表：
- 注释统计对照
- 重叠与 GO 富集表

论文支撑：Methods（版本/区间算法）· Results（结构统计/一致性）· Discussion（注释选择影响）

## 覆盖（副产物）
本任务预计调用算子 29 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
