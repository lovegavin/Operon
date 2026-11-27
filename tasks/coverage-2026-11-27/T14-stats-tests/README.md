# T14-stats-tests · 统计检验族

## 目标
合成数据表 → 假设检验（参数/非参数/多重比较校正）→ 汇总表与图

## 输入
`input/`（生成脚本 `gen_inputs.py`；真实样例见 `evidence/`）

## 覆盖
- 算子 97 个：见 `operators.txt`
- reader 2 个：见 `readers.txt`
- 机器可读清单：`coverage.json`（验收后把 status 从 planned 改成 passed/failed 并记录 job id）

## 验收标准
1) 每个检验有统计量与 p 值；2) 失败项标注缺依赖；3) 汇总 CSV 落盘

## 运行方式
1. `python gen_inputs.py`（生成最小合法输入）
2. 用 `graphs/` 里的路线图提交作业（GUI / CLI / HTTP / MCP 均可）
3. 产物落 `expected/`，指标写 `evidence/report.md`（含 job id、起止时间、算子清单、失败原因）
4. 更新 `coverage.json` 的 status 与 evidence
