# T07 · 千人基因组 chr22 与身高 GWAS：QC、LD 与 PRS

## 科学问题
1000G chr22 与 GIANT 身高汇总统计上，质控、LD 剪枝与 PRS 能否复现常见变异的多基因信号？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| 1000G chr22 VCF | VCF | 1.1 GB | 1000G open | https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/ALL.chr22.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz |
| GIANT height | TSV | 10 MB | academic use | https://portals.broadinstitute.org/collaboration/giant/images/c/c8/GIANT_HEIGHT_Wood_et_al_2014_publicrelease_HapMapCeuFreq.txt.gz |
| 1000G panel | TSV | 100 KB | 1000G open | https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/integrated_call_samples_v3.20130502.ALL.panel |

引用：
- 1000G chr22 VCF: Auton 2015
- GIANT height: Wood 2014
- 1000G panel: 1000G

## 分析路线
1. VcfReader 读 chr22
2. variant_qc/missingness/hwe/maf
3. ld_calculation/ld_pruning
4. gwas_association
5. prs_scoring
6. variant_annotation
7. 回归/效应量

## 交付
图：
- MAF/缺失率与保留数
- LD 衰减
- PRS 十分位

表：
- 质控表
- PRS 系数与 R²

论文支撑：Methods（数据/QC/LD/PRS）· Results（保留率/LD/PRS）· Discussion（分层与样本量）

## 覆盖（副产物）
本任务预计调用算子 108 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
