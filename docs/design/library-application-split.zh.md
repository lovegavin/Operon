# Operon 库与应用完全分离重构方案

状态：**已确认，进入实施**
目标版本：**库 `0.0.0`，应用 `5.0.0`**
标签规范：

- 库：`operon-library-v0.0.0`
- 应用：`v5.0.0`

## 1. 决策摘要

| 项目 | 结论 |
|---|---|
| 仓库 | 库、应用独立开发、独立构建、独立发布 |
| 库构建 | 由库侧自己的 builder 完成，禁止 import 应用代码 |
| 应用 5.0.0 | 只负责安装、校验、加载、执行，不参与库构建 |
| 旧库 | **5.0.0 全部拒绝**，不做静默 pin 修复 |
| 身份 | 每个 package 一个 canonical `code_sha`，库包、wheel、Routes 完全一致 |
| 用户入口 | 两个 ZIP：库包 + Routes |
| 库版本 | 重置为 `0.0.0` |
| 应用版本 | `5.0.0` |
| 库 tag 前缀 | `operon-library-v` |
| bundle 格式 | `bundle_format=1` |
| 算子协议 | `operator_protocol=3`，revision `3.7` |

## 2. 要解决的问题

8.x 的构建链存在真实耦合：

- `release_library.py` 导入已安装的 `operon`，调用 `build_bundle()`；
- `provider_wheel()` 在应用侧重新计算 wheel 身份；
- 源码、wheel、Routes 三份产物在不同时间、用不同输入构建；
- 没有发布门禁同时校验三份产物。

结果是 8.0.10 出现：

- 库包 descriptor `code_sha` 与 Routes `plugin_lock` 不一致；
- 应用无法证明两者等价；
- 路线导入失败。

根因不是单个算子，也不是 UI，而是**库没有自己的构建权**。

## 3. 仓库边界

```text
operon-library/                  Operon/
  operators/                       operon/              engine
  readers/                         src/web/             installer/API
  routes/                          frontend/            UI
  contracts/                       tests/
  tools/operon_library_builder/    docs/
  tests/
  docs/
```

职责：

| 事项 | 库侧 | 应用侧 |
|---|---|---|
| 算子、Reader 源码 | 拥有 | 不拥有 |
| 描述符、文档 | 生成 | 只读取 |
| bundle 格式 | 定义、版本化 | 只读取 |
| `code_sha` | 计算 | 只读取，禁止重算 |
| wheel/entry point | 构建 | 安装，禁止改写 |
| Routes/pin | 构建 | 导入，禁止重生成 |
| 安装/加载/执行 | 不负责 | 负责 |
| 环境安装 | 声明 | 执行 |
| 发布门禁 | 执行 | 消费证据 |

只允许共享**版本化的 JSON Schema 和协议文档**，不共享 builder、运行时代码或构建脚本。

## 4. 两个 ZIP 的契约

### 4.1 库包

文件名：

```text
operon-library-v0.0.0.zip
```

这是一个通用纯 Python 包，不再区分 Linux/Windows。平台相关依赖放入环境声明。

结构：

```text
operon-library-v0.0.0.zip
  library.json
  descriptors.json
  environments.json
  wheels/
    operon_core-0.0.0-py3-none-any.whl
    operon_readers-0.0.0-py3-none-any.whl
    ...
  docs/
  SHA256SUMS
```

`library.json` 示例：

```json
{
  "format": "operon.library",
  "bundle_format": 1,
  "library_version": "0.0.0",
  "operator_protocol": {"version": 3, "revision": "3.7"},
  "minimum_application": "5.0.0",
  "builder": {"name": "operon-library-builder", "version": "1.0.0"},
  "packages": [
    {
      "name": "operon-core",
      "version": "0.0.0",
      "wheel": "wheels/operon_core-0.0.0-py3-none-any.whl",
      "wheel_sha256": "...",
      "code_sha": "...",
      "entry_points": {
        "interface_alanine_scan": "operon_core.steps.interface_alanine_scan:InterfaceAlanineScanStep"
      }
    }
  ]
}
```

规则：

- `code_sha` 是唯一身份，应用不得从安装后的字节重算。
- `wheel_sha256` 只用于完整性，不进入 pin 身份。
- `entry_point` 是 wheel 内真实模块路径，应用按原样加载。
- 禁止应用侧 `provider_wheel()` 重写路径或重新计算 hash。

### 4.2 Routes 包

文件名：

```text
operon-routes-v0.0.0.zip
```

结构：

```text
operon-routes-v0.0.0.zip
  routes.json
  routes/
    assembly_ngx_qc.operon.zip
    ...
  SHA256SUMS
```

每个 route zip 仍包含：

```text
graph.json
parameters.json
execution.json
```

`execution.json` 的 `plugin_lock` 必须直接复制库 manifest 的身份：

```json
{
  "package": "operon-core",
  "version": "0.0.0",
  "code_sha": "..."
}
```

pin 中不允许出现 wheel `sha256`。Routes builder 只能从同一份库 manifest 取身份，不能查询已安装应用。

## 5. 库侧独立 builder

库侧新增：

```text
operon_library_builder/
  identity.py
  wheel.py
  descriptors.py
  routes.py
  gate.py
  cli.py
```

命令：

```bash
python -m operon_library_builder build  --source . --output dist/
python -m operon_library_builder verify --dist dist/
python -m operon_library_builder gate   --dist dist/
```

硬性要求：

- 不得 `import operon`；
- 不依赖已安装 Studio；
- 固定 builder 版本；
- 同一源码 + 同一 builder 可复现相同 `code_sha`；
- `gate` 发现 manifest、wheel、Routes 任一身份不一致即失败。

### 身份定义

对每个 package，按排序后的相对路径和文件内容计算：

```text
sha256( for each file: path + "\0" + content + "\0" )
```

排除：

- `__pycache__`
- `*.pyc`
- build/dist
- 测试缓存
- VCS 元数据

同一个值写入：

1. `library.json` 的 package 记录；
2. wheel 内的 `operon_identity.json`；
3. 该 package 的所有 route pin。

## 6. 应用 5.0.0 的职责

应用只提供两个通用入口：

```text
install_library(zip_path) -> LibraryInstall
install_routes(zip_path)  -> RouteInstall
```

### install_library

1. 校验 `SHA256SUMS`；
2. 读 `library.json`；
3. 校验 `format`、`bundle_format`、`operator_protocol`、`minimum_application`；
4. 用通用 wheel 安装器安装到托管环境；
5. 注册 descriptor 和 canonical entry point；
6. 记录 `{library_version, code_sha, install_root}`。

### install_routes

1. 校验 `routes.json` 和每个 route zip；
2. 读取 `execution.json`；
3. 要求每个 pin 的 `(package, version, code_sha)` 与已安装库完全相等；
4. 不一致立即报错，不猜测、不迁移、不刷新；
5. 注册 graph，不执行。

### 旧库处理

5.0.0 拒绝所有旧库，包括：

- 任意 `library-v8.*`；
- 未知 `bundle_format`；
- 不兼容的 operator protocol；
- 缺少 `code_sha` 的 legacy wheel。

错误必须明确：

```text
This library bundle uses the legacy 8.x format.
Install an operon-library-v0.0.x bundle built for Operon 5.0.0.
```

应用不提供静默 pin 修复路径。

## 7. 版本与标签

| 产物 | 版本 | 标签 |
|---|---|---|
| 库 | `0.0.0` | `operon-library-v0.0.0` |
| 应用 | `5.0.0` | `v5.0.0` |
| bundle 格式 | `1` | 不单独打 tag |
| 算子协议 | `3` / revision `3.7` | 不变 |

规则：

- 库 tag 必须匹配 `^operon-library-v[0-9]+\.[0-9]+\.[0-9]+$`；
- 应用 tag 必须匹配 `^v[0-9]+\.[0-9]+\.[0-9]+$`；
- 旧 `library-v8.*` 标签永久冻结，不移动、不复用；
- 库与应用独立发版；
- `minimum_application` 必须是已经存在的版本，不能标未来版本。

## 8. 用户导入流程

用户只需要：

1. 下载 `operon-library-v0.0.0.zip`；
2. 下载 `operon-routes-v0.0.0.zip`；
3. 应用中选择“导入算子库”，选第一个 ZIP；
4. 应用中选择“导入路线”，选第二个 ZIP；
5. 应用自动完成 wheel 安装、算子注册、pin 校验、环境准备和路线注册。

不需要：

- 用户安装 Python；
- 用户执行 pip；
- 用户手工配置路径；
- 用户处理 pin；
- 第三个依赖包。

可选的 Quickstart/Audit 可以单独发布，但不属于导入契约。

## 9. 发布门禁

### 库侧 CI

1. 单元、契约、组合、依赖、route 测试；
2. 连续构建两次，产物 SHA 必须相同；
3. `gate`：manifest、每个 wheel、每个 route pin 的 `code_sha` 完全一致，mismatch 0；
4. 检查 builder 没有 `import operon`；
5. 检查 descriptor 和文档完整；
6. 只发布两个必需 ZIP + `SHA256SUMS.txt`。

### 应用侧 CI

1. 下载已发布的库 ZIP 和 Routes ZIP；
2. 在干净 5.0.0 profile 中导入两个 ZIP；
3. 断言没有手工 pin 修复；
4. 跑固定 smoke routes；
5. 升级应用 patch 版本，再导入同一对 ZIP；
6. 断言 ZIP 未变化、库未重建。

### 发布验收

不能用源码树构建代替发布验收。必须使用冻结的已发布 ZIP，在干净 profile 安装后执行，沿用 `five-layer-test-standard.md` 的 L5 定义。

## 10. 迁移步骤

### Phase 0：冻结

- 8.0.10 保持不可变，标记为 legacy；
- 8.0.11 不发布；
- 保存 8.0.11 未提交改动为归档 patch，不进入新线。

### Phase 1：抽库

- 建立 `operon-library` 独立仓库；
- 迁入算子、Reader、Routes、描述符、文档；
- 不改算子算法和 ID；
- 加入 `operon_library_builder`；
- 生成 `0.0.0` 并通过 identity gate。

### Phase 2：应用 5.0.0

- 增加通用 `install_library` / `install_routes`；
- 删除运行时 builder 调用；
- 删除 `provider_wheel` 身份重写；
- 删除 `load_entry_point` 兼容补丁；
- 拒绝所有旧库并给出迁移提示。

### Phase 3：联合验收

- 发布 `operon-library-v0.0.0`；
- 发布应用 `v5.0.0`；
- Linux/Windows 干净 profile 各跑一遍两个 ZIP 导入和 smoke routes；
- 记录 SHA、安装路径、pin、运行产物。

### Phase 4：清理

- 删除旧构建脚本和双身份逻辑；
- 更新 CI、文档、帮助文本；
- 保留 8.x 迁移说明。

## 11. 测试矩阵

| 领域 | 测试 |
|---|---|
| builder 隔离 | builder 不得 import `operon` |
| 身份 | manifest、wheel、route pin 完全一致 |
| 可复现 | 两次构建 SHA 相同 |
| 安装 | 库 ZIP 安装到干净 5.0.0 profile |
| Routes | 导入时零 pin 修复 |
| 执行 | 至少 8 条代表 route |
| 升级 | 5.0.1 导入同一对 ZIP，库不重建 |
| 负例 | 篡改 ZIP、错误协议、缺失 pin、旧 8.x 库 |
| 平台 | Linux 和 Windows 干净 profile |

## 12. 完成标准

- 库侧不 import 应用代码即可构建；
- `operon-library-v0.0.0` 与 `v5.0.0` 已发布；
- 两个 ZIP 在干净 Linux/Windows 环境可导入、可运行；
- manifest、wheel、Routes 身份 mismatch 为 0；
- 应用升级不要求重建库；
- 5.0.0 对所有旧库给出明确拒绝信息；
- 用户只需两个 ZIP，后续全部由应用完成。
