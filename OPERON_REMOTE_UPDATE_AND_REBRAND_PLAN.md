# Operon 远程全量更新与命名迁移方案

> 状态：设计稿（本轮不实现）  
> 依据版本：`3.1.6-bf2ffb73d361`  
> 目标：远端更新时，用本地算子库、版本号与 catalog/pin 清单**完整覆盖**远端；命名统一为 Operon；文档分类重整。

## 0. 结论摘要

当前画布 `interface all` 的 `selected environment is unavailable` 不是 SSH、输入文件或连线问题，而是：

1. 远端 `licai-srv-test` 的 managed code 仍是旧构建（`structure_interface_core code_sha=cc73...`），当前前端是 `136abefe...`；
2. 远端算子库仍是旧 provider/旧 descriptor；当前图的 `plugin_lock` 也保存了旧 pin；
3. 现有更新流程只“补缺”，不会用本地库完整覆盖远端，也不会刷新旧 pin。

**算子库结论：需要更新，但不是缺算子。**

| 层面 | 结论 | 依据 |
|---|---|---|
| 远端库 | **必须全量替换** | 远端 `code_sha=cc73...`、旧 provider；与本地 3.1.6 不兼容 |
| 本地库功能 | **不需要新增算子** | 当前画布用到的 `structure_interface_core`、`structure_paratope_predict`、`structure_disorder_profile`、`join`、`aggregate` 本地都有 |
| 本地库身份/打包 | **需要重建、升版** | 7 个 `operon-* 1.0.0` wheel、1171 descriptors 已安装，但 seed、bundled history、provider 仍带旧名/旧 pin |
| 图 pin | **需要迁移** | 旧 `code_sha`/旧 provider 的 pin 不可复用；`setdefault` 不会刷新已有 pin |

因此需要：**新的 Operon library bundle + library version bump + 远端全量替换 + pin 迁移**。不需要新增算子逻辑。

## 1. 命名决定

目标态只使用 **Operon**；不再保留旧名的运行时兼容。

- 主包：`operon`
- SDK：`operon_sdk`
- CLI：`operon`（不再提供旧 CLI 别名）
- MCP：`operon_*` 工具与资源标识
- HTTP/agent API：`/api/...`、scope 名称统一为 Operon
- 工作流/算子 ID：`operon.*`；旧 `*.` ID 由一次性迁移器转换，不保留运行时别名
- 插件 provider / wheel 包：`operon-*`
- 环境变量：`OPERON_*`
- Profile：`%USERPROFILE%\.operon\profiles`
- SSH 协议帧：`OPERON-*`
- 文档、UI、错误文案、安装回执：只出现 Operon

迁移分三层，避免“只改表面、运行时仍然混用”：

1. **展示层**：UI、README、文档、错误文案、日志。
2. **代码层**：包名、import、CLI、MCP、模块路径、测试。
3. **持久化契约**：算子 ID、provider、wheel 名、环境变量、profile、协议帧、已保存工作流与 pin。第三层必须配一次性迁移器和回滚，不做运行时双读。

## 2. 目标架构：不可变 Build

更新单位不是“代码文件”，而是：

```text
Build = {
  build_id,
  application: { source_sha256, version },
  library:     { bundle_sha256, library_version, package_count, descriptor_count },
  catalog:     { digest, operator_count },
  environment: { python, platform, dependency_lock }
}
```

远端布局：

```text
<managed_root>/
  builds/<build_id>/
    code/                 # 完整源码，不含缓存
    env/                  # 该 build 专用环境
    library/              # 完整 registry + sources + wheels
    manifest.json         # 上述 Build 清单
  current -> builds/<build_id>
  previous -> builds/<old_build_id>
```

规则：

- `build_id` 由 `application.source_sha256 + library.bundle_sha256 + catalog.digest + library_version` 计算；任一项变化即新 build。
- 激活前逐项校验 manifest：文件 sha、wheel sha、descriptor 的 `code_sha` / `implementation.sha256` / `declaration_sha` / `execution_sha`、provider、版本。
- 校验失败不切换 `current`；旧 build 保留给运行中的 job。
- 切换用原子 `os.replace`/symlink；失败可回滚到 `previous`。
- 不再复用旧 `server.json` 的 `app_dir`，除非它的 `build_id` 与本地 manifest 完全一致。

## 3. 远端更新流程

```text
本地：
  1. 构建 library bundle（完整 sources + packages + manifest）
  2. 计算 BuildManifest / build_id
  3. 上传 code archive + library bundle + manifest

远端：
  4. 解包到 builds/<build_id>/（不碰 current）
  5. 建 env，安装 application 依赖
  6. 安装完整 library bundle（替换，不是补缺）
  7. 逐项校验 manifest
  8. 原子切换 current
  9. 写安装回执（build_id、sha、时间、结果）
 10. 握手返回 build_id + catalog digest
```

`/connect` 与 `/install` 的语义要分开：

- `/connect`：只连接，**不更新**；发现 build_id 不一致时返回 `stale_build`，不静默复用旧 code。
- `/install`：执行上述全量部署；返回 build_id 与进度。
- 前端在 `stale_build` 时提示“需要升级远端”，而不是把节点标成 `selected environment is unavailable`。

## 4. 源码改动点

以下路径相对当前主包根；行号基于 3.1.6 当前文件。

| 文件 | 改动 |
|---|---|
| `remote/provision.py` | `locate()` 读取 `server.json` 后必须比对 `build_id`/`source_sha256`；不一致返回 `stale_build`，不再直接复用。`provision()` 增加 `library_bundle` 与 `manifest` 参数；解包后先校验再切换。 |
| `remote/install_linux.py` | 增加 `--manifest`、`--library-bundle`；安装 code 后调用 library bundle 安装；不再只装 code+seed；写回执时记录 build_id、bundle sha、library version。 |
| `remote/library.py` | 新增 `replace()`：按 bundle 全量替换 registry/sources/packages；`compare()` 增加 `code_sha`、`implementation.sha256`、version、wheel sha 比较；`install_selected()` 保留给“补缺”，但 `/install` 不再走它。 |
| `library_bundle.py` | 复用 `build_bundle()` / `unpack_bundle()` / `install_bundle()`；bundle 增加 `manifest.json` 与 catalog digest；`build_bundle` 同时从已安装 registry 与 source tree 收集，确保 7 个 wheel 都进 bundle。 |
| `remote/server.py` | 新增 `library_replace` RPC（或让 `library_install` 接受 bundle）；新增 `build_info`；`library_manifest` 返回 build_id/library version/catalog digest。 |
| `remote/handshake.py` | 握手参数与响应增加 `build_id`、`source_sha256`、`library_bundle_sha256`、`catalog_digest`；`catalog_unchanged` 只在 build_id 一致时成立。 |
| `remote/client.py` | 连接时发送本地 `build_id`；缓存 key 加 build_id；build 不一致不得复用 `cached_info['catalog']`。 |
| `src/web/remote_service.py` | `connect(install=True)` 触发全量部署；`prepare()` 在 build_id 变化时刷新 pin；`check_library()` 返回“可替换/需替换”而不只是 missing；UI 暴露 build 状态。 |
| `src/web/remote_api.py` | `/install` 返回 build_id、阶段、错误码；新增 `/build` 查询。 |
| `plugins.py` / `packages.py` | `provider_identity()` 取消隐式别名；seed 重建为 Operon；`bundled_state()` 只读新 seed；旧名不再参与 identity。 |

## 5. Pin 迁移

远端切换 build 后，旧图的 `plugin_lock` 不能继续使用。迁移规则：

1. 以算子 ID 为键，查新 catalog；
2. 若 ID 未变且新 descriptor 的 `implementation.sha256` 与旧 pin 相同，保留；
3. 若 ID 未变但实现变了，替换为新 descriptor，并记录 `migrated_from`；
4. 若 ID 已改（`operon.*` 迁移），按映射表换键；
5. 找不到新实现时，节点标 `unavailable` 并给出 operator ID，不静默删除；
6. `RemoteManager.prepare()` 在 build_id 变化时执行上述迁移；`setdefault` 只用于新节点，不用于已有 pin。

## 6. 命名迁移工作分解

全仓旧名残留约 **5874 次 / 2209 个文件**，其中：

- MCP 工具名：424 次 / 128 文件
- 包名：1176 次 / 924 文件
- 环境变量：299 次 / 123 文件
- `.旧名` 路径/后缀：79 次 / 49 文件
- 展示名：2172 次 / 1162 文件
- Python import：418 次 / 134 文件
- 协议/JSON：435 次 / 175 文件

按目录：`library/` 3395、`docs/` 1370、主包 619、`src/` 195、`scripts/` 96、`examples/` 85。

执行顺序：

1. **冻结**：新分支，先不改行为，只加 Build/库替换。
2. **代码层 codemod**：包目录、import、CLI、MCP、模块路径、测试；用 AST/正则组合，逐包跑测试。
3. **持久化契约**：算子 ID、provider、wheel 名、env、profile、协议帧；配一次性迁移器与回滚。
4. **展示层**：UI、README、文档、错误文案、日志。
5. **CI 门禁**：除 `docs/archive/` 与迁移器 fixture 外，禁止旧名；`grep` 命中即失败。
6. **版本**：主版本 bump（建议 4.0.0），发布说明明确 breaking change。

## 7. 文档整理分类

目标树：

```text
docs/
  README.md                 # 索引：主题、读者、状态、最后验证版本
  user/                     # 安装、快速开始、画布、工作流、作业、结果、服务器
  agent/                    # agent API、bootstrap、operations、environment repair、headless
  developer/                # 插件、package protocol、library、registry、design
  reference/                # 算子目录、API、large resources、result viewers
  operations/               # 远程执行、readiness、resource runtime、troubleshooting
  release/                  # changelog、release notes
  archive/                  # 旧发布说明、历史审计、过期设计
```

规则：

- 一个主题只保留一个 canonical 页面；重复页合并或移入 `archive/`。
- 每页头部写 `audience`、`status`、`last_verified`。
- `docs/releases/` 264 篇按年份归档；旧发布说明不参与改名，只加“历史文档”标记。
- `docs/rebranding.md` 改为“命名政策与迁移记录”，不再作为兼容性承诺。
- 文档中的代码路径统一用目标态路径；迁移前的当前路径只在迁移器映射表中出现。

## 8. 实施顺序与验收

**阶段 A：Build + 全量库替换（不改命名）**

1. 实现 manifest/build_id 与远端 `builds/` 布局。
2. 接入 library bundle 到 `/install`。
3. 握手校验 build_id；`prepare` 刷新 pin。
4. 在 `licai-srv-test` 上做一次完整替换，重跑当前画布。

验收：

- `selected environment is unavailable` 消失；
- 远端 catalog 的 `code_sha`、`implementation.sha256`、provider、library version 与本地逐项一致；
- 旧图 pin 自动迁移，主/敏感性作业可重跑；
- 回滚到 `previous` 可用。

**阶段 B：命名迁移**

5. 代码层 codemod + 测试。
6. 持久化契约迁移器 + 旧图转换。
7. 展示层与文档迁移。
8. CI 门禁与 4.0.0 发布。

验收：

- 产品/UI/新文档/新算子 ID 中无旧名；
- 旧工作流经迁移器转换后可运行；
- `docs/` 新树链接检查通过；
- 除 `archive/` 与迁移 fixture 外，全仓 grep 无旧名。

## 9. 当前画布的临时处理

在 Build 流程上线前，不要手工改 pin 或远端 registry。建议：

1. 先通过前端“升级/修复远端环境”触发一次全量部署；
2. 部署后刷新当前图 `plugin_lock`；
3. 再 validate/run；
4. `join/aggregate` 的 `('Form', 'dims contain duplicates')` 是独立的图级问题，等环境恢复后单独修。
