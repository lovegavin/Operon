# T28 · reader 一致性：110 个真实样例文件的可读性验证

## 科学问题
对库内 110 个 reader，用其格式的真实官方样例文件验证可读性（shape/metadata/类型），哪些格式缺样例或解析失败？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| 格式样例目录 | mixed | 随格式 | 见上游 | tasks/real-2026-11-27/T28/input |

引用：
- 格式样例目录: 各数据源

## 分析路线
1. 按 reader 清单准备真实样例
2. 逐个读入
3. 记录 shape/metadata/异常
4. 通过率与缺口统计

## 交付
图：
- reader 通过率条形图
- 失败分类图

表：
- reader 验证表（格式/样例/sha256/shape/status）

论文支撑：Methods（样例来源）· Results（通过率）· Discussion（缺口）

## 覆盖（副产物）
本任务预计调用算子 15 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
