# T14 · 研究汇总：13 个真实任务的可复现研究报告

## 科学问题
如何把 T01–T13 汇总成可复现报告，使每个数字都能追溯到 job id、算子与产物？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| T01–T13 产物 | mixed | 随上游 | 见上游 | tasks/real-2026-11-27/*/expected |

引用：
- T01–T13 产物: 本仓库

## 分析路线
1. report_manifest/data_dictionary
2. report_generate_markdown/report_generate_html
3. figure_bundle/table_bundle
4. bundle_checksum

## 交付
图：
- 报告结构图
- 数字→job→算子→文件 追溯链

表：
- 素材清单（文件/大小/sha256/来源 job）

论文支撑：Methods（打包与追溯）· Results（完整性校验）· Discussion（可复现性）

## 覆盖（副产物）
本任务预计调用算子 6 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
