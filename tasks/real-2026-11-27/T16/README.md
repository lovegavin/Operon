# T16 · 基因组组装质控：真实组装体的连续性评估

## 科学问题
在真实基因组组装（GRCh38 chr21 与一个细菌完成图）上，N50/NGx、gap、contig 长度分布能否区分完成图与草图？组装指标对下游注释影响多大？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| GRCh38 chr21 | FASTA | 900 MB | GENCODE open | https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_49/GRCh38.p14.genome.fa.gz |

引用：
- GRCh38 chr21: Frankish 2019

## 分析路线
1. FastaReader
2. assembly_stats/contig_stats/ngx/gapstats/length_bins
3. kmer 统计
4. contiguity 汇总

## 交付
图：
- NGx 曲线
- contig 长度分布
- gap 密度

表：
- 组装指标表
- 完成图 vs 草图对照

论文支撑：Methods（组装指标定义）· Results（连续性）· Discussion（对注释影响）

## 覆盖（副产物）
本任务预计调用算子 18 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
