# T20 · 免疫组库：真实 AIRR 数据的克隆型与多样性

## 科学问题
真实 AIRR 重排数据上，CDR3 克隆型、多样性与 V/J 使用能否复现原文？不同深度下多样性估计偏差多大？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| AIRR example | TSV | 2 MB | CC BY 4.0 | https://raw.githubusercontent.com/airr-community/airr-standards/master/examples/AIRR-seq/PBMC_IgG.tsv |

引用：
- AIRR example: AIRR Community

## 分析路线
1. AirrReader
2. cdr3_properties/clonotype
3. diversity/rarefaction
4. vj_usage
5. 统计与图

## 交付
图：
- 克隆型大小分布
- 多样性稀释曲线
- V/J 使用热图

表：
- 克隆型表
- 多样性汇总

论文支撑：Methods（AIRR/克隆型）· Results（多样性/使用）· Discussion（深度偏差）

## 覆盖（副产物）
本任务预计调用算子 1 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
