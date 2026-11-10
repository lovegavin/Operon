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
git -C /home/gavin/Operon switch -c library/7.0.15-operon library-v7.0.15

# 2. 删除旧 seed
rm -rf library/seed/biopipe

# 3. 替换 12 个旧 import
grep -RIl 'biopipe' library/seed/src library/seed/operon \
  | xargs sed -i 's/biopipe_sdk/operon_sdk/g; s/biopipe/operon/g'

# 4. 确认无旧名
grep -RIn 'biopipe' library/seed/src library/seed/operon

# 5. 用 3.1.9 的打包器生成原生 bundle
cd /home/gavin/Operon-3.1.6
PYTHONPATH=. python3 - <<'PY'
from operon.library_bundle import build_bundle
print(build_bundle(
    '/home/gavin/Operon/library/seed',
    '/home/gavin/lib7015-native',
    '7.0.15',
))
PY
```

本机已经用上述方式生成过一个验证包：

```text
/home/gavin/lib7015-native/Operon-Library-v7.0.15.operon-library.zip
sha256: 87fe054a0829d29efc58c773347f6067ebb617838b95ea52c6eca870740ec2c9
packages: 7
descriptors: 1171
```

这个包还没有做安装和路线回归，下一步应先验证它。

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

## 六、SSH 报错说明

SSH 的 `TypeError` **不是算子库问题**。

`src/web/remote_service.py:198` 把非 `RemoteError` 异常统一包装成：

```python
f'SSH 连接失败：{type(exc).__name__}。请核对主机、认证方式及远端环境。'
```

真实堆栈被吞掉了。等算子库更新完成后，需要单独用相同连接参数复现，拿到 `TypeError` 的具体文件和行号；这一步不需要改前端。

## 七、当前建议

1. 先按本文更新 7.0.15 算子库并生成原生 bundle。
2. 在 3.1.9 上完成安装 + 路线导入验收。
3. 算子库通过后，再处理 SSH TypeError 和卸载 MCP 提示。
4. 最后整体发布 3.1.10，前端暂不改动。
