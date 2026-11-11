# Operon 8.0.0 算子库集成问题总结

## 结论

8.0.0 库的算子、路线和源码结构已经迁移到 Operon，但**库的打包产物还不适合直接作为应用内置库使用**。应用 4.0.0 直接加载 8.0.0 源码时会出现两类问题：

1. `builtin_packages.json` 里的 `code_sha` 与源码树计算出的 `code_hash` 不一致，运行时报 `Implementation code hash mismatch`。
2. 79 条内置路线中，有 3 条与 8.0.0 的算子契约不一致；`routes800.zip` 中也有 3 条路线无法注册。

这不是前端问题，也不是 SSH 问题。

## 问题一：descriptor 哈希与源码不一致

官方 8.0.0 的 `library/seed/operon/builtin_packages.json` 中，所有 descriptor 的 `code_sha` 都是同一个 provider-wheel 摘要，例如 `c651c34f8c5d7ff8...`。但应用从源码树加载 `missing` / `describe` 时，按实际源文件计算出的 `code_hash` 是 `43c701272eb6d88d...`，校验直接失败：

```text
ValueError: Implementation code hash mismatch: missing
ValueError: Implementation code hash mismatch: H5adReader
```

原因：8.0.0 的 manifest 是按 **provider wheel 布局**生成的；4.0.0 把库作为 **源码树** 内置，加载器却复用同一份 manifest。

临时处理：

```bash
PYTHONPATH=. python3 scripts/build_builtin_packages.py --refresh
```

该命令会按源码树重新生成 descriptor，`demo` 路线随之恢复正常。但它一次改写了 **1,489 个文件**（163,087 insertions / 67,487 deletions），包括：

- `library/seed/**` 的声明文件；
- `operator_index.json`、`reader_index.json`、`builtin_packages.json`；
- `library/seed/src/web/builtin_routes.json`（新增约 40,605 行）；
- 声明升级到 `protocol_revision: 3.7`，并加入 `data_formats`；
- 部分依赖元数据被清空，例如 `zivot_andrews` 的 `statsmodels>=0.14`。

因此不能简单把这份 refresh 结果当作发布内容，必须由库的构建流程生成与源码一致的 manifest。

### 建议库侧修复

1. 发布源码树内置库时，`builtin_packages.json` 的 `code_sha` 必须使用源码树 `code_hash`，不能使用 wheel 摘要。
2. 增加一个 CI 用例：用应用 4.0.0 的 `operon_sdk.declarations.code_hash` 读取 8.0.0 源码，逐个校验 descriptor。
3. 若仍需保留 wheel manifest，应让应用区分“源码库”和“wheel 库”两种加载路径，不要共用一份 descriptor。

## 问题二：3 条内置路线契约不兼容

应用启动时安装 79 条内置路线，以下 3 条被跳过：

| 路线 | 错误 |
| --- | --- |
| `route_88fb083f4238` | 缺少 `info.missing_code` |
| `route_bf78f7a6e12f`（生存分析） | 缺少 `OS_Time_nature2012`、`OS_event_nature2012`、`AJCC_Stage_nature2012` |
| `route_f6f466bace35`（GWAS） | 缺少 `info.missing_code` |

当前应用把这 3 条降级为警告并继续启动，其余 76 条正常安装。但这意味着 8.0.0 的路线模板仍引用旧算子输入字段或旧参数名。

### 建议库侧修复

1. 用 8.0.0 算子重新生成这 3 条路线的 `parameters.json` / `task.yaml`。
2. 对每条路线做一次 `compile_graph`，把 `GraphError` 作为库构建失败，而不是留到应用启动时。
3. 生存分析路线需要把临床字段改成 8.0.0 Reader 实际输出的字段名。

## 问题三：routes800.zip 中 3 条路线注册失败

把 `Operon-Routes-v8.0.0.zip` 整体导入时，76 条成功，3 条失败：

- `gwas.operon.zip`：`输入输出契约不兼容：需要数值张量；缺少 info.missing_code...`
- `proteomics_de.operon.zip`：`Choose a Reader for input meta; multiple Readers match: TsvFileReader, TxtReader`
- `survival.operon.zip`：缺少上述 3 个临床字段。

应用侧已经做了两件事：

- 路线导入改为逐条隔离，单条失败不再中止整个 zip，返回 `routes` 与 `failed`；
- Reader 选择增加 `source.dims` 与 Reader `ndim` 的消歧，解决 VCF 的 `VcfFileReader` / `VcfReader` 二义性。

但 `proteomics_de` 的 `.txt` 表格二义性仍未解决，需要库侧明确 Reader 或补 `dims`。

## 已确认不属于库的问题

`test_hot_builtin_wheels_preserve_disk_and_stream_and_old_lock` 和
`test_external_sdk_resource_package_runs_compressed_source` 仍失败，原因是应用示例插件的宿主约束还写着：

```text
operon-studio>=3.0.0,<4
```

应用已经是 4.0.0，需要把 3 个示例的约束改为 `<5`。这与 8.0.0 库无关。

## 当前 4.0.0 验证状态

- 应用版本：4.0.0
- 内置库：8.0.0，1,063 operators / 108 Readers / 79 routes
- 启动：成功；76 条内置路线安装，3 条跳过
- `demo` 工作流：`status: complete`
- 路线 zip：76 条注册成功，3 条失败
- 焦点测试：修复哈希后，6 个失败用例中 4 个通过；剩余 2 个是示例宿主约束问题
- 分支：`release/4.0.0-app`，未提交、未打标签

## 建议顺序

1. 库侧先修 manifest 哈希和 3 条路线契约。
2. 应用侧只保留逐条隔离导入和 Reader 消歧，不把 `--refresh` 的 1,489 文件改动直接提交。
3. 库修好后重新跑 4.0.0 启动、路线导入、安装/卸载和远端部署。
4. 最后再发 4.0.0 和 GitHub Release。
