# 现状与解耦交接：Operon Studio 5.1.5 + Operator Library 0.1.0

- 应用：**Operon Studio 5.1.5**（tag `v5.1.5` → `5073a9a9`，`latest`）
- 主库：**0.1.0**（tag `operon-library-main-v0.1.0` → `0b6a8a0c`）
- 测试分支库：**fork1-v0.0.0**（tag `operon-library-fork1-v0.0.0` → `0b6a8a0c`）
- `main`：`5073a9a9`，本地与 `origin/main` 一致
- 契约：`protocol_version=3`、`protocol_revision=3.7`、`bundle_format=1`
- 主库规模：1066 operators / 108 Readers / 1174 descriptors / 7 packages / 79 routes

> 本文是交接主文档，描述**现在是什么、边界在哪、重构时必须守住什么**。
> 历史变更见 `01-application-changes-3.1.6-to-5.1.5.md` 与
> `02-library-changes-7.0.1-to-0.1.0.md`。

## 1. 一句话架构

```text
┌─────────────────────────────┐        ┌──────────────────────────────┐
│ Operon Studio（应用）        │        │ Operator Library（库）        │
│ 安装 / 校验 / 执行 / 展示     │◀───────│ 算子 + Reader + 文档 + 路线    │
│ 不构建库、不算库身份          │  两个  │ builder 算身份、出 wheel、出包  │
└─────────────────────────────┘   ZIP   └──────────────────────────────┘
```

应用是**通用运行时**：它不知道“8.0.x 的 pin 该换成什么”，也不应该知道。
库是**自包含产物**：它不依赖应用源码，构建时不 `import operon`。

## 2. 仓库与代码地图

| 路径 | 职责 | 归属 |
|---|---|---|
| `operon/` | 引擎、作业、准入、共享池、远程、库安装、MCP/CLI/HTTP 适配 | 应用 |
| `operon_sdk/` | 协议声明、哈希、字节码、worker 运行时 | 共享（版本化） |
| `src/web/` | Web 服务、作业服务、远程管理、库/路线 API | 应用 |
| `src/task/step/steps/`、`src/reader/readers/` | 内置算子/Reader 源码（仅用于构建库） | 库 |
| `library/seed/` | 主库源码树 + 路线模板 + 文档 | 库 |
| `library/forks/fork1/` | fork1 测试库源码树 | 库 |
| `operon_library_builder/` | 独立 builder：identity / wheel / descriptors / manifest / gate | 库 |
| `scripts/package_route_collection.py` | 路线集合打包（pin 来自库 manifest） | 库 |
| `scripts/package_server.py` | 服务端 zip（app wheel + library wheel） | 应用 |
| `scripts/package_release.py`、`build_setup.py`、`build_runtime.py` | Windows payload / Setup / runtime | 应用 |
| `frontend/` | React UI | 应用 |
| `desktop/` | WebView 宿主（.NET） | 应用 |
| `docs/handover/` | 本交接文档 | 双方 |

> 当前 builder 仍在同一 monorepo 里，但它是独立 Python 包、无 `import operon`。
> 应用栈重构时可以把 `operon_library_builder/` + `library/` 整体迁到独立仓库，
> 应用只保留“读 manifest、装 wheel、装库”的代码。

## 3. 库包契约（唯一接口）

### 3.1 文件

```text
operon-library-<name>-v<version>.operon-library.zip
├── library.json
├── SHA256SUMS
├── wheels/
│   ├── operon_core-<ver>-py3-none-any.whl
│   ├── operon_readers-<ver>-py3-none-any.whl
│   └── ...
├── documentation/...
├── environments.json
└── icons/...
```

### 3.2 `library.json`

```json
{
  "format": "operon.library",
  "bundle_format": 1,
  "library_name": "main",
  "library_version": "0.1.0",
  "minimum_application": "5.0.0",
  "operator_protocol": {"version": 3, "revision": "3.7"},
  "packages": [
    {
      "name": "operon-core",
      "version": "0.1.0",
      "wheel": "wheels/operon_core-0.1.0-py3-none-any.whl",
      "wheel_sha256": "...",
      "code_sha": "...",
      "entry_points": {"join": "operon_core.steps.join:JoinStep"}
    }
  ]
}
```

规则：

- `format` 必须是 `operon.library`；
- `bundle_format` 必须是 `1`（应用拒绝未知值）；
- `library_name` 由 builder 写入；旧包缺失时按 `main` 处理；
- `minimum_application` 由应用比较，低于当前版本直接拒绝；
- `packages[].code_sha` 是唯一身份，应用不重算；
- `entry_points` 是 wheel 内真实模块路径，应用不改写。

### 3.3 路线集合

```text
operon-routes-<name>-v<version>.zip
├── routes.json          # library_name / library_version / routes[]
├── README.md
├── SHA256SUMS
└── routes/*.operon.zip  # 每个恰为 graph.json / parameters.json / execution.json
```

`execution.json` 的 `plugin_lock` 只能是
`{"package": "...", "version": "...", "code_sha": "..."}`，且必须与已安装库精确相等。

## 4. 身份与版本规则

1. **库身份**：每个 package 的规范化源码哈希 → `code_sha`；同一份源码 + 同一 builder → 同一值。
2. **库标签**：`<library_name>-v<library_version>`，例如 `main-v0.1.0`、`fork1-v0.0.0`。
3. **应用版本**：独立 semver，5.x 与库版本无关。
4. **路线 pin**：直接复制库身份，不二次计算。
5. **发布门禁**：manifest ↔ 每个 wheel ↔ 每条 route pin 的 `code_sha` 必须完全一致；不一致禁止发布。

## 5. 应用侧消费链

### 5.1 安装

```text
POST /api/libraries/install (multipart file)
  → install_library(manager, path)
    1. 解包、校验 SHA256SUMS / format / bundle_format / protocol / minimum_application
    2. 读取 library_name / library_version → 目标标签
    3. 冲突检查：id、distribution、顶层 module、主名称
    4. 安装全部 wheel 到 <library>/environments/<generation>/code
    5. 从 wheel 重建 descriptors，写 registry / packages / operators
    6. 写 libraries/<label>/{library.json,version.json,archive.zip}
    7. 更新 library_release 摘要
```

- 失败会回滚刚落下的 `libraries/<label>`，不留下“有 archive 没 registry”的孤儿。
- 同标签 + 同 sha + wheel 已存在 → 幂等返回，不重装。
- 8.x 包直接 `LegacyLibrary` 拒绝，文案指向“安装当前 operon-library bundle”。

### 5.2 存储布局

```text
<install>/versions/<version>/
├── library/
│   ├── registry.json                 # 当前库状态（packages/descriptors/libraries/library_release）
│   ├── libraries/<label>/
│   │   ├── library.json
│   │   ├── version.json
│   │   └── archive.zip               # 原始导入包
│   ├── operators/<id>.json           # 逐算子来源与哈希
│   ├── operators/index.json
│   ├── packages/<digest>/<wheel>
│   ├── environments/<generation>/code # pip 安装的 wheel
│   ├── documentation/
│   └── base/                         # 仅安装包自带，首次启动 bootstrap
├── runtime/python/...
└── frontend/...
```

workspace 只放用户数据：

```text
<workspace>/<task>/
├── input/
├── results/<job-id>/
├── runs/<job-id>/                    # 可复现骨架
│   ├── run.json
│   ├── job.json
│   ├── graph.json
│   ├── parameters.json
│   ├── plugins.lock.json
│   └── logs/README.txt
└── analysis/                         # agent 通过 MCP 提取的中间数据
```

### 5.3 base 库

- payload 里 `library/base/operon-library-main-v0.1.0.operon-library.zip`；
- 首次启动 `_bootstrap_base_library()`：若 `libraries` 为空且无 marker，则安装该 bundle；
- marker：`<plugin directory>/base-library.json`；
- 失败只 warn，不阻塞启动；用户仍可手动导入。

## 6. 多算子库规则

- 所有库**地位相同**，没有 active 指针；`libraries` 列表就是全部。
- 主名称来自库包，不由用户输入。
- 主名称不得重复；id / distribution / 顶层 module 也不得重叠：

```text
LibraryConflict: {kind: identifier|package|module|library, id, library}
```

- 删除一个库只移除该分支的 descriptors/packages/目录，其他库继续可用。
- 路线 pin 与“当前库集合”精确匹配；任何一个 pin 找不到对应身份，导入即拒绝。

## 7. 执行、provenance 与共享池

### 7.1 运行

- 画布 `graph.json` 的 `plugin_lock` 为空；提交时按 id 在当前库集合中解析。
- 结果：`<task>/results/<job-id>/`。
- 运行元数据：`.studio/jobs/<job-id>/{job.json,plugins.lock.json,logs}`。

### 7.2 provenance（只记录本次用到的）

`job.json`：

```json
"plugins": {
  "generation": "...",
  "libraries": ["main-v0.1.0"],
  "operators": {
    "join": {
      "library": "main-v0.1.0",
      "package": "operon-core",
      "version": "0.1.0",
      "code_sha": "...",
      "declaration_sha": "...",
      "execution_sha": "...",
      "sha256": "..."
    }
  }
}
```

`run.json` 同源，另带 `results` / `metadata` 相对路径。

### 7.3 共享池

- 每个 workspace 注册时携带 `library_root`；
- pool 持久化 `WorkspaceSpec.library_root`，重启后恢复；
- `manifest_only_registry` 仅在无 `library_root` 时为 true；
- 库切换/导入期间若有活动任务，pool 拒绝变更（先结束任务）。

### 7.4 远端

- `source_archive()` 打包：应用源码 allowlist + `library/operon-library-<label>.operon-library.zip` 各分支；
- 服务端 `install_linux.py` 安装全部分支到 `code/library`；
- `RemoteService` 构造 `Settings(library_root=code/library, manifest_only_registry=False)`；
- `build_identity` 从 `library/registry.json` 计算库身份，再与桌面 `expected` 比较；
- 库变更后 `RemoteManager.invalidate_build()`，避免“本地程序在准备期间发生变化”。

## 8. 对外接口

| 层 | 接口 |
|---|---|
| HTTP | `GET /api/libraries`、`POST /api/libraries/install`、`DELETE /api/libraries/{name}`、`POST /api/routes/import-collection` |
| HTTP v1 | `GET /api/v1/libraries`、`POST /api/v1/libraries`、`DELETE /api/v1/libraries/{name}`、`POST /api/v1/routes/import-collection` |
| CLI | `operon library install|list|remove`、`operon routes import` |
| MCP | `operon_library_install`、`operon_library_list`、`operon_library_remove`、`operon_routes_import` |
| 错误 | `409 library_conflict`（带 conflicts）、`404 library_missing`；8.x 返回 422 并给出迁移文案 |

## 9. 发布与构建流水线

### 9.1 库

```bash
python -m operon_library_builder build \
  --source library/seed \
  --version 0.1.0 \
  --minimum-application 5.0.0 \
  --name main \
  --output build/lib

python -m operon_library_builder gate --dist build/lib
python -m operon_library_builder gate --dist build/lib   # 两次构建 SHA 必须相同

python scripts/package_route_collection.py \
  --library build/lib/operon-library-main-v0.1.0.operon-library.zip \
  --output build/routes
```

### 9.2 应用

```text
frontend: npm run build → frontend/dist
wheel:    python -m build --wheel
server:   scripts/package_server.py --app-wheel ... --library-wheel ... --output ...zip
windows:  build_runtime.py → package_release.py --desktop <dir> --runtime ... \
          --base-library ... → build_setup.py
publish:  scripts/release_proxy/publish_release.py publish ...
```

### 9.3 发布资产

- 应用：`Operon_Setup-<ver>.exe`、`Operon-<ver>-Server.zip`、`operon_studio-<ver>-py3-none-any.whl`、`SHA256SUMS.txt`
- 库：`operon-library-<name>-v<ver>.operon-library.zip`、`SHA256SUMS.txt`（主库带路线集合）

## 10. 完全解耦的核心关键

1. **两条版本线**：应用 semver 与库 semver 独立，tag 前缀不同（`v*` / `operon-library-*`）。
2. **唯一接口是格式 1 的 ZIP**：应用不读库源码，不跑库构建脚本。
3. **身份只算一次**：builder 产出 `code_sha`；应用只读，禁止重算、禁止改写 entry point。
4. **两个 ZIP 导入**：库 + 路线集合；路线只引用身份，不携带实现。
5. **应用无 seed**：内置库也是一个普通 bundle（`library/base`），走同一条 `install_library` 路径。
6. **版本作用域存储**：库在 `<install>/versions/<ver>/library`，workspace 只放数据。
7. **多库等地位**：主名称来自库包，id/包/模块/主名称不得重叠；没有 active 指针。
8. **pin 精确匹配**：路线 pin 必须与已安装库完全一致；证明不了就拒绝，不做“猜”的迁移。
9. **环境由库声明、应用创建**：`environments.json` + `resources.environment`；失败不回退共享解释器。
10. **远端交付原始分支 archive**：服务端安装同一批 bundle，身份与桌面一致；不再依赖源码 seed。
11. **provenance 在运行时绑定**：画布不 pin；每个 job 记录实际使用的库/版本/哈希。
12. **格式变更显式拒绝**：8.x 直接报错并给迁移文案；未知 `bundle_format`/协议同样拒绝。

## 11. 测试与验收现状

已覆盖：

- builder：构建、gate、可复现、wheel 内容；
- 库安装：单库/多库/冲突/删除/迁移/8.x 拒绝；
- 应用分离：payload 无 seed、安装后 1174 descriptors、路线 79 条；
- run skeleton：used-only provenance、绝对/相对 base_dir、只读目录不阻塞提交；
- 共享池：`library_root` 持久化与恢复、活动任务拒绝切换；
- 前端：`tsc` + 34 文件 / 215 测试（5.1.2 基线），5.1.5 定向 19 测试；
- Windows：5.1.2/5.1.4/5.1.5 干净安装、库导入、VHH 路线 5/5、CSV 哈希
  `faa7bd4f…2ce2c2e`；
- 远端：5.1.3/5.1.4 实际安装，`server.json` 记录 `fork1-v0.0.0+main-v0.1.0`。

未覆盖/已知债务：

- 库审计 L3 覆盖率 794/1063，269 条 SKIP（缺数据/工具/权重），逐条有原因；
- 5.1.5 之后没有重跑完整 Windows Python 全量套件；
- 远端共享池在“库导入 + 旧 pool 记录”组合下仍需先清池；
- 发布依赖本机 18080 代理与 `%USERPROFILE%\.operon` 凭据；
- 8.x 线冻结，不再修；迁移只保 0.x。

## 12. 应用栈重构交接清单

### 必须保留（否则破坏已有安装）

- `bundle_format=1` 的读取与校验语义；
- `code_sha` 只读、entry_point 原样加载；
- `library_release` / `libraries` / `operators` 元数据字段；
- 版本作用域路径 `<install>/versions/<ver>/library`；
- 主名称不重复、id/包/模块不重叠的冲突规则；
- 8.x 拒绝文案与 `legacy_library` 错误码；
- `job.json` / `run.json` 的 provenance 字段；
- 路线集合的 `routes.json` + 三文件 bundle 契约。

### 可以替换

- Web 框架、路由组织、前端 UI、桌面宿主；
- 作业调度与共享池实现（只要保留 `WorkspaceSpec.library_root` 语义）；
- 远端传输实现（只要仍交付原始 branch archive 并在服务端安装）；
- 包管理/venv 细节（只要仍按库声明创建环境）。

### 禁止

- 用应用侧逻辑重算 `code_sha` 或重写 `entry_point`；
- 用 `refresh_missing` 兜底一个错误的库发布；
- 让用户给库起任意名字（名字只能来自 `library.json`）；
- 回退共享解释器执行声明了 `resources.environment` 的算子；
- 把库装进 workspace 或 `.studio`。

## 13. 快速自检

```bash
# 库是否存在且身份一致
operon library list

# 当前 workspace 的 job provenance
python - <<'PY'
import json, pathlib
p = pathlib.Path(r'<workspace>/.studio/jobs/<job-id>/job.json')
j = json.loads(p.read_text(encoding='utf-8'))
print(j['plugins']['libraries'])
print(list(j['plugins']['operators'])[:5])
PY

# run skeleton
ls <workspace>/<task>/runs/<job-id>/
```

## 14. 版本坐标

| 对象 | 版本 | tag / 提交 |
|---|---|---|
| 应用 | 5.1.5 | `v5.1.5`（annotated `00af5700`）→ `5073a9a9` |
| 主库 | 0.1.0 | `operon-library-main-v0.1.0`（`4eed1756`）→ `0b6a8a0c` |
| fork1 | 0.0.0 | `operon-library-fork1-v0.0.0` → `0b6a8a0c` |
| 旧库基线 | 7.0.1 | `library-v7.0.1` → `8133781c` |
| 旧应用基线 | 3.1.6 | `v3.1.6` → `0f2c87cd` |

