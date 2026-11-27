# T12 · 真实脑 MRI 体积测量

## 科学问题
MNI152 T1 上阈值/形态学分割与体积测量能否给出稳定灰白质比并与文献一致？配准误差如何影响体积？

## 真实数据
| 数据集 | 格式 | 规模 | 许可 | URL |
| --- | --- | --- | --- | --- |
| MNI152 T1 2mm | NIfTI | 10 MB | FSL academic | https://raw.githubusercontent.com/neurospin/brainomics_data/master/MNI152_T1_2mm.nii.gz |

引用：
- MNI152 T1 2mm: Mazziotta 2001

## 分析路线
1. NiftiReader
2. resample/smoothing
3. threshold/morphology
4. segmentation/volume
5. registration
6. 统计与切片

## 交付
图：
- 原始/直方图/阈值切片
- 分割标签与体积条形图

表：
- 体积统计与文献对照

论文支撑：Methods（数据/重采样/分割）· Results（体积比/误差）· Discussion（单受试者偏差）

## 覆盖（副产物）
本任务预计调用算子 9 个，见 `operators.txt`；实际调用在 `coverage.json` 的 `actual_operators`。
