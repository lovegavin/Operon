# T22 · 统计检验与回归在真实临床数据上的适用性

## 科学问题
在真实 NHANES 子集上，不同正态性/方差齐性检验如何影响两组比较与回归模型的选择？错误选择会带来多大偏差？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| NHANES PAQ | XPT | 5 MB | public domain | https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/PAQ_J.xpt |

引用：
- NHANES PAQ: CDC NHANES

## 分析路线
1. XptReader
2. descriptive_stats/normality_test/variance_test
3. 两组检验（t/Welch/Mann-Whitney/Kruskal/Brunner-Munzel…）
4. 多组检验（ANOVA/Welch/Kruskal/Friedman…）
5. 相关/回归（线性/稳健/logistic/Cox）
6. 多重校正与效应量

## 交付
图：
- 分布诊断图
- 检验 p 值矩阵对比
- 回归系数森林图

表：
- 检验结果表
- 方法选择决策表

论文支撑：Methods（数据/检验族）· Results（选择敏感性）· Discussion（报告规范）

## 覆盖（副产物）
本任务预计调用算子 145 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
