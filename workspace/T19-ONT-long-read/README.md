# T19 · 长读长数据：真实 ONT 读段的组装与注释

## 科学问题
真实 ONT 读段（ENA）上，读段 QC、组装与基因注释能否给出连贯的细菌基因组？与参考完成图比较误差在哪里？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| ENA ONT 读段 | FASTQ | 500 MB | ENA open | https://ftp.sra.ebi.ac.uk/vol1/fastq/ERR/0/ERR/ERR10141077.fastq.gz |

引用：
- ENA ONT 读段: EBI

## 分析路线
1. FastqReader
2. read_qc/length_quality
3. assembly_contig_stats/ngx
4. gene_prediction/annotation
5. 参考比较

## 交付
图：
- 读段长度/质量分布
- 组装 N50 与累计长度
- 注释基因密度

表：
- 读段 QC 表
- 组装/注释统计

论文支撑：Methods（读段/组装/注释）· Results（连续性/注释）· Discussion（长读长误差）

## 覆盖（副产物）
本任务预计调用算子 16 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
