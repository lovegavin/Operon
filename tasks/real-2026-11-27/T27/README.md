# T27 · NHANES 调查数据的完整统计工作流：从原始 XPT 到可发表表格

## 科学问题
真实 NHANES 2017-2018 多文件（人口学、体测、问卷）合并后，描述统计、分布诊断、关联检验与加权回归能否形成可复现的流行病学分析表？表格操作在真实调查数据上的坑是什么？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| NHANES DEMO_J | XPT | 3 MB | public domain | https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DEMO_J.xpt |
| NHANES BMX_J | XPT | 3 MB | public domain | https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BMX_J.xpt |
| NHANES PAQ_J | XPT | 5 MB | public domain | https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/PAQ_J.xpt |

引用：
- NHANES DEMO_J: CDC
- NHANES BMX_J: CDC
- NHANES PAQ_J: CDC

## 分析路线
1. XptReader 读三个文件
2. join/merge/select/derive
3. 缺失编码与清洗
4. descriptive_stats/groupby/pivot
5. normality/variance/两组与多组检验
6. weighted regression
7. Table 1

## 交付
图：
- 样本流程图
- 关键变量分布
- Table 1

表：
- Table 1
- 关联检验表

论文支撑：Methods（权重/合并）· Results（基线/关联）· Discussion（调查数据特殊性）

## 覆盖（副产物）
本任务预计调用算子 29 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
