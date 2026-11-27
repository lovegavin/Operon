# T18 · 表观遗传学：甲基化芯片与差异甲基化

## 科学问题
真实 450K 甲基化数据（GEO）上，β 值归一化、差异甲基化与 CpG 岛注释能否复现原文？批次与细胞组成如何影响结论？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| GEO 甲基化矩阵 | matrix | 5 MB | GEO public | https://ftp.ncbi.nlm.nih.gov/geo/series/GSE1nnn/GSE111629/matrix/GSE111629_series_matrix.txt.gz |
| Illumina 450K manifest | CSV | 100 MB | Illumina | https://webdata.illumina.com/downloads/productfiles/humanmethylation450/humanmethylation450_15017482_v1-2.csv |

引用：
- GEO 甲基化矩阵: GEO
- Illumina 450K manifest: Illumina

## 分析路线
1. 读 β 矩阵与 manifest
2. bisulfite_conversion_rate
3. 归一化/差异甲基化
4. CpG 岛/基因注释
5. 统计与火山图

## 交付
图：
- β 分布
- 差异甲基化火山图
- CpG 岛注释

表：
- 差异甲基化表
- 注释汇总

论文支撑：Methods（芯片/归一化）· Results（DMP/DMR）· Discussion（细胞组成）

## 覆盖（副产物）
本任务预计调用算子 7 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
