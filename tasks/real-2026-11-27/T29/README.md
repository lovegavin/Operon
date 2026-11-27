# T29 · 出版级图表与表格：从真实结果到论文素材

## 科学问题
把 T01–T28 的真实结果整理成出版级矢量图与可导出表，统一风格、单位、误差表示与图注，能否满足期刊要求？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| T01–T28 产物 | mixed | 随上游 | 见上游 | tasks/real-2026-11-27/*/figures |

引用：
- T01–T28 产物: 本仓库

## 分析路线
1. 读取结果表
2. 绘图（bar/box/violin/scatter/heatmap/line/volcano/forest/ROC）
3. 样式与导出（PDF/PNG/SVG）
4. 表格格式化

## 交付
图：
- 统一风格示例图组
- 图注与单位检查

表：
- 图表清单（文件/尺寸/格式/来源 job）

论文支撑：Methods（图形规范）· Results（素材清单）· Discussion（可读性）

## 覆盖（副产物）
本任务预计调用算子 32 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
