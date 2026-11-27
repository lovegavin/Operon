# T17 · 测序数据 QC：真实 BAM 与 ATAC/ChIP 峰

## 科学问题
在真实比对文件（1000G chr22 BAM 子集、ENCODE ATAC BAM）上，flagstat/覆盖/峰识别与 FRiP 能否复现公共 QC 指标？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| ENCODE ATAC BAM | BAM | 300 MB | ENCODE open | https://www.encodeproject.org/files/ENCFF356LFX/@@download/ENCFF356LFX.bam |

引用：
- ENCODE ATAC BAM: ENCODE 2012

## 分析路线
1. BamReader
2. bam_flagstat/read_length/gene_bias
3. coverage/peak_call/peak_quality
4. atac_peak_call
5. FRiP 与峰注释

## 交付
图：
- flagstat 汇总
- 覆盖曲线
- 峰数与 FRiP

表：
- QC 指标表
- 峰表

论文支撑：Methods（比对/峰识别）· Results（QC/峰）· Discussion（批次）

## 覆盖（副产物）
本任务预计调用算子 60 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
