# T24 · 流式细胞术与电生理：真实 FCS/EDF 信号处理

## 科学问题
真实流式数据（FlowRepository）与 EEG（PhysioNet）上，门控/补偿与滤波/事件检测能否复现原文结论？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| FlowRepository FCS | FCS | 20 MB | CC BY 4.0 | https://flowrepository.org/fcs/FR-FCM-ZY3P/example.fcs |
| PhysioNet EEG | EDF | 10 MB | ODC-BY | https://physionet.org/files/eegmmidb/1.0.0/S001/S001R01.edf |

引用：
- FlowRepository FCS: FlowRepository
- PhysioNet EEG: Schalk 2009

## 分析路线
1. FcsReader/EdfReader
2. 流式门控/补偿
3. EEG 滤波/伪迹/事件检测
4. 统计与图

## 交付
图：
- FSC/SSC 门控图
- EEG 功率谱/事件检测

表：
- 门控统计表
- 信号 QC 表

论文支撑：Methods（门控/滤波）· Results（分群/事件）· Discussion（阈值敏感）

## 覆盖（副产物）
本任务预计调用算子 14 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
