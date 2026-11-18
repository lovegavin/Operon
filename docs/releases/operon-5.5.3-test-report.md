# Operon Studio 5.5.3 — test report

## Scope

| Field | Value |
| --- | --- |
| Release under test | Operon Studio 5.5.3 |
| Operator library | `main-v0.1.30` (7 packages, 1,069 operators, 108 readers, 1,177 descriptors) |
| Route collection | `main-v0.1.30` (79 routes) |
| Platform | Windows 11, Python 3.11 runtime shipped with the installer |
| Install root | a disposable directory outside the source tree |
| Evidence | one JSON file per probe, written next to the installer output |

The release turns the separate *Large resources* settings page into a section of
the **Runtime status** panel, links at the granularity upstream maintains
(`tree` or `items`), drops the allow-list, and decides link state from the file
system so links created outside the UI are visible.

## Artifacts

| Artifact | Bytes | SHA256 |
| --- | --- | --- |
| `Operon-Studio-v5.5.3-Windows-x64.zip` | 357,285,339 | `d75cb8227e3f4d4bf4129c727a566cdb1a14365ba5c47dc6fecc2654118c7973` |
| `Operon_Setup-5.5.3.exe` | 429,062,697 | `201e556eb3b452c93f7a83a1619dc60925ba5ed95a9e2808398a56573477fa64` |
| `Operon-5.5.3-Server.zip` | 4,736,227 | `8448cb55f2f3be0cf8fcb85f1481cb82833434847f789c219f640d2585e7abfa` |
| `operon_studio-5.5.3-py3-none-any.whl` | 989,048 | `7d30c39ea36de004c2c01bda576678f7833f043ecb1c936a282a28a8151edef8` |
| `operon-library-main-v0.1.30.operon-library.zip` | 6,936,080 | `5cea2be45b80932018cac2f3fa59eb9e81464f51186c1de41e2755b68eb12b0a` |
| `operon-routes-main-v0.1.30.zip` | 201,625 | `ed94bc0767a7a6dfd23aa24fd20f707d3476462973a26b0120dfaeeebabb308a` |

The four Windows artifacts are listed in `SHA256SUMS-5.5.3.txt`; the two library
artifacts are listed in `library-0.1.30-SHA256SUMS.txt`.

## Phase 1 — clean install

- Installer exit code `0`. A silent install of an earlier build of this tree measured
  **18.28 s** from process start to exit; the final build reported
  `{"status": "installed"}` and its setup log spans 88.4 s including the runtime
  self-check that runs on the first install of a rebuild.
- Version directory: `versions/5.5.3-<build>`; `/api/version` returned
  `{"version": "5.5.3", "build": "<build>", "display": "5.5.3 (<build>)"}`.
- Desktop server ready 26 s after the installer returned (first probe:
  `{"version": "5.5.3", ...}`).

## Phase 2 — library and API contract

`GET /api/v1/large-resources` (session token required):

| Field | Result |
| --- | --- |
| Resources | 16 |
| `state` present | 16 (`missing` 12, `downloaded` 3, `partial` 1) |
| `link_unit` present | 16 (`tree` 10, `items` 6) |
| `units` present | 16 |
| `root_linked` / `root_target` / `link_target` present | 16 each |
| `environments` present | 16, union `antifold`, `boltz`, `colabfold`, `esmfold`, `openfold` |
| `/api/environments` | 7 environments, all `missing` on a fresh install |

The `units` array carries one entry per declared link unit with `name`, `state`,
`source` and `receipt`; `receipt: false` marks a link Operon did not create.

## Phase 3 — UI: resources inside Runtime status

Captured with headless Edge at 1440×900:

| Check | Result |
| --- | --- |
| Release label | `5.5.3` |
| Settings navigation | 服务器, 输出与查看器, 外观, 语言 — **no 大型资源 entry** |
| Runtime status shows 大型资源与模型权重 | yes |
| Execution location selector | `本地` only (no server configured) |
| Environment groups | `antifold`, `boltz`, `colabfold`, `esmfold`, `openfold`, plus one group for resources without an environment |
| Resource rows | 16 (10 whole-tree rows, 6 per-item rows) |
| Badges | `缺失` 12, `已下载` 3, `部分就位` 1 |
| Per-item rows | list each declared file with its own state and a `链接` action |
| Whole-tree rows | single `链接已有目录` action; `解除链接` appears when linked |
| Link dialog | asks for one absolute path, shows the suggested location, the link unit and the 链接/取消 buttons |
| Console errors | none (`modal-error` count 0) |

## Phase 4 — linking behaviour

Library-level checks against a temporary resource root:

| Case | Result |
| --- | --- |
| `link(..., unit="tree")` | `{"status": "linked", "unit": "tree", "mode": "symlink"}` |
| state after tree link | `state: linked`, `root_linked: true`, one unit `tree` with `receipt: true` |
| `unlink(..., unit="tree")` | `{"status": "unlinked", "mode": "symlink"}`; state back to `missing` |
| `link(..., unit="<file>")` | `{"status": "linked", "unit": "esm2_t6_8M_UR50D.pt", "mode": "hardlink"}` |
| state after item link | `linked: true`, unit `state: linked`, the remaining expected file reported as not linked |
| link created by hand (`ln -s`) | `state: linked`, `linked: true`, `target` shown, `receipt: false` |
| source outside any allow-list | accepted (the allow-list check is gone); absolute/existing/no-overlap rules still enforced |

## Phase 5 — operator library `main-v0.1.30`

- `resources.json` declares `link_unit` for all 16 resources (10 `tree`,
  6 `items`); `release.json` is `0.1.30` with `minimum_application` and
  `build_application` both `5.5.3`.
- `resource_link.py` accepts `unit`, skips the allow-list when the caller does
  not pass one, records `units` in the receipt, and can drop a single unit.
- `_resources_common.py` exposes `link_unit_of`, `link_units`, `state`,
  `root_linked`, `root_target` and per-unit `state`.
- Bundle: 7 packages, 1,177 descriptors, 6,936,080 bytes; route collection: 79
  routes, 201,625 bytes, pins rewritten from the same library build.

## Phase 6 — automated tests

| Suite | Result |
| --- | --- |
| `tests/test_resource_units.py tests/test_remote_resources.py tests/test_resource_api.py tests/test_resource_link_control_api.py tests/test_environment_api_runtime.py tests/test_bridge_remote_resources.py tests/test_environment_install.py` | 49 passed |
| `tests/test_manifest_registry.py tests/test_registry_layout.py tests/test_registry_maintenance.py tests/test_builtin_routes.py` | 30 passed, 1 failed |
| frontend `npm test` | 43 files, 266 tests passed |

The single failure, `test_manifest_only_refresh_discovers_added_source_and_publishes_generation`,
also fails on a pristine checkout of `v5.5.2` (`git worktree add --detach`), so it
is an environment-dependent pre-existing failure and not a regression of this
release.

## Defects fixed

| Id | Symptom | Cause | Fix |
| --- | --- | --- | --- |
| F-22 | The resource dialog could narrow to an environment and then show no resource, or offer a resource that environment does not use. | The environment list was built from environment status only. | The list only offers environments that still have a missing linkable resource, and the resource list is filtered by the resource's environments. |
| F-23 | A resource linked with `ln -sfn` was reported as missing. | Link state came from the receipt written by the link helper. | State now comes from the file system (`root_linked`, per-unit `linked`); the receipt only adds provenance. |

## Not tested

- Linking through a real remote profile: no SSH profile is configured on this
  machine, so remote link/unlink ran only through unit tests against the bridge
  and the remote dispatch.
- A complete install of a multi-gigabyte environment through the new UI.
- Windows junction targets on a network share (junctions need a local volume).

## Verification commands

```
Operon_Setup-5.5.3.exe --quiet --install-dir <stage> --no-register --result <evidence>\install-result.json
python api_check.py      # reads <evidence>\api.json; writes the resource contract
python ui_check.py       # headless Edge; writes <evidence>\ui.json and two screenshots
pytest tests/test_resource_units.py tests/test_remote_resources.py tests/test_resource_api.py -q
```
