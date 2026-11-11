# Operon Library 7.0.15 原生迁移说明

## 结论

当前 3.1.9 遇到的算子库导入错误和路线导入错误，根因都在 **7.0.15 算子库仍按 3.1.6 的 biopipe 目录和 import 方式构建**，不是前端问题。

7.0.15 需要重新发布一个 **Operon 原生包**：

- 安装包后缀保持 `operon-library.zip`
- 包内只保留 `sources/operon/**`
- 源码只 import `operon` / `operon_sdk`
- 用当前 3.1.9+ 的 `build_bundle` 重新生成 bundle 和 provider wheels
- 版本仍为 `7.0.15`，保持 1063 个算子 / 108 个 Reader

在算子库更新并验证通过前，前端和 3.1.9 应用代码不改。

## 一、算子库导入错误

### 现象

```text
Unexpected library file: sources/biopipe/builtin_packages.json
```

### 原因

7.0.15 的 seed 目录同时存在：

```text
library/seed/biopipe/builtin_packages.json
library/seed/operon/builtin_packages.json
```

旧的 `release_library.py` 会打包整个 seed，所以官方包中带上了：

```text
sources/biopipe/builtin_packages.json
```

而 3.1.9 的 `operon/library_bundle.py:unpack_bundle()` 只接受：

```text
sources/operon/**
packages/*.whl
library.json
```

看到 `sources/biopipe/...` 会直接判定为非法文件并拒绝整个包。

### 修复

1. 从 `library-v7.0.15` 建一个库发布分支。
2. 删除/排除 `library/seed/biopipe/`，只保留 `library/seed/operon/`。
3. 重新打包，确认 zip 内不存在 `sources/biopipe/`。
4. 不要通过修改 3.1.9 的导入器去接受旧目录，否则会把旧格式重新带回新版本。

## 二、7.0.15 源码仍引用 biopipe

7.0.15 的 `library/seed/src` 中还有 12 个文件引用旧模块：

```text
library/seed/src/task/step/steps/esmfold_predict.py
library/seed/src/task/step/steps/proteinmpnn_design.py
library/seed/src/task/step/steps/_native_results.py
library/seed/src/task/step/steps/peptide_modified_mass.py
library/seed/src/task/step/steps/peptide_fragment_ions.py
library/seed/src/task/step/steps/rfdiffusion_design.py
library/seed/src/task/step/steps/peptide_isotope_envelope.py
library/seed/src/task/step/steps/_export_domain.py
library/seed/src/task/step/steps/_ms_utils.py
library/seed/src/task/step/steps/export_results.py
library/seed/src/task/step/steps/_plot_helpers.py
library/seed/src/task/step/steps/vcf_normalize.py
```

需要替换：

```text
biopipe_sdk  -> operon_sdk
biopipe.     -> operon.
from biopipe -> from operon
import biopipe -> import operon
```

这些 import 在 3.1.9 中不存在；即使强行让 bundle 导入成功，运行到这些算子时仍会失败。

## 三、路线 zip 报错

### 现象

```text
Required plugin versions are unavailable; install the original packages.
Unknown or wheel pins are not automatically replaced.
```

抛出位置：

```text
operon/pins.py:173
```

### 原因

路线 zip 的 `plugin_lock` 记录了制作路线时的算子实现指纹，其中包括 `code_sha`。

- 路线是在 7.0.15 算子库上制作的，pin 指向 7.0.15 的实现。
- 当前安装的是 3.1.9 内置库 `2026.11.8.1`，同一个算子 ID 的 `code_sha` 不同。
- `operon/pins.py` 的 `matches()` 对 bundled 算子要求 `code_sha` 完全一致，因此拒绝路线。

这是连锁错误：

```text
7.0.15 算子库导入失败
        ↓
7.0.15 算子没有安装
        ↓
路线 pin 与 3.1.9 内置库不一致
        ↓
路线保存/注册失败
```

### 修复

先让原生 7.0.15 可安装，再导入路线：

1. 安装原生 `Operon-Library-v7.0.15.operon-library.zip`。
2. 确认 7 个 provider 包全部启用。
3. 再导入 7.0.15 路线 zip。
4. 如果路线仍报 pin 错误，说明路线包本身不是在这次原生 7.0.15 上生成的，需要用原生 7.0.15 重新导出路线包。

## 四、推荐的库发布流程

```bash
# 1. 从 library-v7.0.15 建分支
git -C the 7.0.15 source worktree switch -c library/7.0.15-operon library-v7.0.15

# 2. 删除旧 seed
rm -rf library/seed/biopipe

# 3. 替换 12 个旧 import
grep -RIl 'biopipe' library/seed/src library/seed/operon \
  | xargs sed -i 's/biopipe_sdk/operon_sdk/g; s/biopipe/operon/g'

# 4. 确认无旧名
grep -RIn 'biopipe' library/seed/src library/seed/operon

# 5. 用 3.1.9 的打包器生成原生 bundle
cd the 4.0 worktree
PYTHONPATH=. python3 - <<'PY'
from operon.library_bundle import build_bundle
print(build_bundle(
    'the 7.0.15 source library/seed',
    'a local lib7015-native directory',
    '7.0.15',
))
PY
```

本机已经用上述方式生成过一个验证包：

```text
a local lib7015-native directory/Operon-Library-v7.0.15.operon-library.zip
sha256: 87fe054a0829d29efc58c773347f6067ebb617838b95ea52c6eca870740ec2c9
packages: 7
descriptors: 1171
```

这个包已安装到 `/tmp/operon7015-test`，7 个 package 安装成功；但应用启动在内置路线编译阶段失败，见第六节。路线导入尚未开始。

## 五、验收清单

### 包检查

```text
[ ] zip 内没有 sources/biopipe/
[ ] library.json format = operon.library
[ ] version = 7.0.15
[ ] 7 个 provider 包
[ ] 1171 个 descriptors（1063 算子 + 108 Reader）
[ ] 每个 wheel 都能在 3.1.9 中 import
```

### 3.1.9 安装检查

```text
[ ] /api/plugins/install 接受该 bundle
[ ] 安装后 7 个包全部 enabled
[ ] 算子列表包含 1063 个算子
[ ] Reader 列表包含 108 个 Reader
[ ] 随机抽取旧 biopipe import 的算子，实际运行通过
```

### 路线检查

```text
[ ] 7.0.15 路线 zip 可导入
[ ] 路线注册成功
[ ] 路线中的 plugin_lock 与已安装 7.0.15 的 code_sha 匹配
[ ] 路线可保存、可重新打开
```

## 六、原生 7.0.15 安装后的启动错误

原生 7.0.15 包可以安装成功，`plugin install` 返回 7 个 package，但 3.1.9 启动时会在内置路线编译阶段失败：

```text
src.web.graph.GraphError: 输入输出契约不兼容：需要数值张量；缺少 info.missing_code；Both ports must declare data_formats before format adaptation
```

堆栈位置：

```text
src/web/routes.py:461 install_builtins
src/web/graph.py:256 compile_graph
```

原因不是 7.0.15 包损坏，而是 3.1.9 应用自带的 `src/web/builtin_routes.json` 路线模板，仍然按 3.1.9 内置算子的端口和 `data_formats` 编写。7.0.15 替换算子后，端口契约发生变化，这些应用内置路线无法再编译。

原生 7.0.15 bundle 目前只包含算子包，不包含 `builtin_routes.json` 或路线模板，因此安装它不会替换 3.1.9 应用内置的旧路线。

库侧需要从以下两种方式中选一种，并在发布前验证：

1. 在 7.0.15 原生包中提供与 7.0.15 算子契约一致的 `builtin_routes.json`，由安装过程替换应用内置路线；或
2. 先在库侧更新路线模板，再同步更新 3.1.9 应用的 `src/web/builtin_routes.json`。

无论采用哪种方式，验收都必须覆盖：安装 7.0.15 后应用能启动、内置路线可编译、7.0.15 路线 zip 可导入和注册。

## 七、SSH 报错说明

SSH 的 `TypeError` **不是算子库问题**。

根因在 `operon/remote/client.py:75`：它把 build identity 作为第 5 个位置参数传给 `provision()`，但 `provision(connection, profile, progress, cancel, root=None, expected=None)` 的第 5 个参数是 `root`。首次部署时 `root` 收到 dict，随后 `Path(dict)` 触发 `TypeError`，又被 `src/web/remote_service.py:198` 包装成 `SSH连接失败：TypeError`。

已在 `release/3.1.10` 分支修复为 `expected=self.build or None`，并增加参数断言测试。`tests/test_remote_installation.py` 16 passed；远端相关测试合计 42 passed，3 个失败是既有的 remote fixture 版本不匹配，与本次修复无关。

## 八、当前建议

1. 先按本文更新 7.0.15 算子库，生成只含 `sources/operon/**` 的原生 bundle。
2. 同时解决 7.0.15 算子契约与内置路线模板不兼容的问题，否则应用安装后会启动失败。
3. 在 3.1.9 上完成安装、启动、路线导入验收。
4. SSH 修复已在 3.1.10 分支完成；卸载前无条件提示断开 DSH / MCP 也已加入 `installer/Program.cs`。
5. 最后整体发布 3.1.10，前端暂不改动。
