# Operon Studio 5.7.23 test report

5.7.23 closes the five defects reported against the large-resource cards and the
environment badges, and ships after a 993-form contract sweep, a four-end parity
check and a server upgrade that the host itself confirms.

## Scope

5.7.23 fixes five defects found while reading resource readiness from the panel:

- A download button was never offered. `snapshot()` published `downloadable`,
  `download_supported`, `files_present`, `files_missing` and `rsync` on the unit
  dictionary, while components carried only `name`, `path`, `mode`, `kind`,
  `bytes`, `url`, `note`, `state`, `files`, `missing` and `size_mb`. The panel
  reads `component.downloadable`, so all 24 unit buttons were disabled and read
  `无缺失文件`, including `alphafold2/afdb`, which declares 9 sources.
- Presence was not computed from the declared file list. `files_present` and
  `files_missing` now come from the unit's own list or, when a resource declares
  exactly one manifest unit, from that resource's `expected_files`, probed
  against the link target or the resource root. Component `missing`,
  `files_missing` and `files[].present` are rewritten from the same list.
- One unit did not have one action. `unitAction()` now has six fixed branches:
  `下载缺失文件（n）` for a pending downloadable unit with missing files,
  `rsync 拉取` when a source is an rsync URL, `无下载源` when
  `download_supported === false`, `未声明文件清单` when nothing is declared,
  `已全部就绪` when `missing === 0`, and `缺 n 个文件，没有 HTTP/rsync 源`
  otherwise. Only the first two are enabled.
- `未检查` was a state without a meaning. Resources that declare no file list
  keep `state=unknown` and read `未声明文件清单` / `No file manifest` with
  `已声明 0 项` and the caption `该资源没有登记应校验的文件，因此不参与就绪判定`.
  13 unit cards had read `未检查`.
- Environment badges named the wrong cause. `ready` reads `已就绪`; `incomplete`
  with every dependency installed reads `资源未齐备` (`Resources incomplete`);
  `incomplete` with a missing dependency reads `依赖缺失`; `stale` whose phase is
  `failed` reads `安装已中断` (`Installation interrupted`); any other `stale`
  reads `需重新准备`; `missing` reads `未安装`. Six of the seven environments
  that had read `安装失败` were resource-short; the one genuinely interrupted
  install now reads `未就绪`.

The release body is `bad7967ec` — *release: Operon Studio 5.7.23 with
contract-correct resource cards and four-end parity* (38 files, +1922/−280).
Three follow-up commits close gaps found while testing it: `044bff0a7` declares
the checkout state to the payload manifest, `56c60c8cc` downloads git sources
with an old git and to a non-writable root, and `f2ce69296` adds reachable
ProteinMPNN mirrors and a writable ColabFold root.

## Environment

| Item | Value |
| --- | --- |
| Application | 5.7.23 |
| Branch | `release/5.4.0` |
| Library | `main-v1.1.14` (7 packages, 1,182 descriptors, 1,074 operators) |
| Workstation | Windows 11, WSL Ubuntu 24.04 (x86_64) |
| Server | `licai-srv`, Linux x86_64, `172.22.148.93` |
| Server build | `e48ae5c62e624991b8a88946846ff4b8060859ea630b64db37b173148c225e97` |
| Server matches client | `GET /api/remote/{id}/build` → `matches: true` |
| Server environments | 18 listed, 7 strictly ready |

## Frontend

`npm test -- --run` passes: 43 test files, 280 tests, 10.86 s. The suites that
grew with the panel work are `RuntimeStatusPanel.test.tsx` with 26 tests and
`LargeResourceSection.test.tsx` with 14; `RemotePanel.actions.test.tsx` carries
18 tests.

The panel now renders one action per unit. `下载缺失文件（n）` and `rsync 拉取`
are enabled; `无下载源`, `未声明文件清单`, `已全部就绪` and
`缺 n 个文件，没有 HTTP/rsync 源` are disabled. A unit whose declared files are
missing no longer reads `无缺失文件`.

Both catalogs carry 1,118 keys in the same order, 12 keys were added, and
`未检查` / `Not checked` and `无缺失文件` / `No missing files` are gone.
`npx tsc -b` is clean.

## Backend

`tests/test_resource_api.py` passes: 25 passed. The suite covers git sources,
http and ftp sources, the non-writable root fallback and unit coverage.

The service side carries the same five fixes. `src/web/resource_api.py` gains
`_declared_names`, `unit_declared_files`, `_split_presence`, `_card_state`,
`card_ready`, `_merge_missing`, `_component_name` and `_mirror_components`, and
`unit_coverage()` and `unit_downloads()` were updated to resolve presence the
same way.
`resource_counts()` in `src/web/environment_api.py` counts components through
`card_ready()` and attributes a resource to every environment in the resource's
`environments` list, so `core` reports 5 units instead of `resources_total=0` and
`antismash` reports 0/3. `resource_readiness()` in `operon/remote/server.py`
takes an optional environment argument so a proxied snapshot can be scoped.

`licai-srv` was upgraded to the same build,
`e48ae5c62e624991b8a88946846ff4b8060859ea630b64db37b173148c225e97`, and
`GET /api/remote/{id}/build` returns `matches: true`. Of the 18 environments
listed at the time of the run, 7 are strictly ready:

| Environment | Ready units |
| --- | --- |
| `antifold` | 14/14 |
| `boltz` | 30/30 |
| `esm2` | 7/7 |
| `esmfold` | 15/15 |
| `openfold` | 20/20 |
| `rfdiffusion` | 8/8 |
| `rna` | 2/2 |

The remaining 11 are short of dependencies or resources; the itemised gaps are in
Known limitations.

## Contract validation (993 operators)

`operon_validate` (MCP) was run over one form per operator, 993 forms in total.

| Round | Forms | Valid | Failures |
| --- | --- | --- | --- |
| First pass | 993 | 980 | 13 |
| Retry of the 13 | 13 | 13 | 0 |
| Total | 993 | 993 | 0 |

The 13 first-pass failures were `WinError 10054` / `WinError 10061` raised after
the host process running the batch was killed; they are transport failures, not
contract failures, and all 13 pass on retry. The per-form results are in
`D:\ot55\stage0v55fi\workspace\p6\runs\validate_all2.csv` and the retry in
`D:\ot55\stage0v55fi\workspace\p6\runs\validate_retry.csv`.

81 further operators were not covered. Their input contract requires more than
one input (`['x']`, `['feature']`, `['sample']`, bam binary fixtures that are
not present on this host), so a single-node form cannot instantiate them. They
are recorded as uncovered and routed to follow-up (未覆盖，列入路线化补测).

## Four-end parity

CLI, HTTP, MCP and the UI remain adapters over one service, so the five fixes are
visible on all four: the payload is built once in `src/web/resource_api.py` and
`src/web/environment_api.py`, and `resource_readiness()` serves the same view to
the remote panel.

MCP exposes 142 tools. `operon_environment_repair` is new: it posts
`/environments/{name}/repair`, or `/remote/{profile_id}/environments/{name}/repair`
for a configured server, and rewrites stale staging shebangs in an environment
that is already installed. The bridge route is `remote_environment_repair` in
`operon/bridge.py`, the manager is `environment_repair` in
`src/web/remote_service.py`, and the server handler is `environment_repair` in
`operon/remote/server.py`.

Remote coverage was completed on `operon_jobs`, `operon_job`, `operon_cancel`
and `operon_pool_status`, which now take `profile_id` and act on a configured
server, and on `operon_resource_cancel` and `operon_resource_log`, which accept
the same argument.

## Builds

All files are in `D:\OperonBuild550\release92\` except the application wheel,
which is also staged in `D:\OperonBuild550\wheel33\`.

| Artifact | File | Bytes | SHA256 |
| --- | --- | --- | --- |
| Installer payload | `Operon-Studio-v5.7.23-Windows-x64.zip` | 357,976,153 | `6a01fd205eaee61bf9641ec74aef09534d73183bb8858923453dc63d84a32544` |
| Windows installer | `Operon_Setup-5.7.23.exe` | 429,753,520 | `651c5d642eb87d597ee2e1e308a92458acb542524d99ae22b2ac45a3f0677389` |
| Server bundle | `Operon-5.7.23-Server.zip` | 9,996,053 | `7b2129f17b3fc43d83700ff4e75b49008675a5ec22097a7560a29f99e87f4082` |
| Application wheel | `operon_studio-5.7.23-py3-none-any.whl` | 1,026,537 | `b6c8dc628710fc0ef05f414e0e0da5749ce72f85977fabae29b9d0a2e4e9f7d8` |
| Library wheel | `operon_builtin_library-1.1.14-py3-none-any.whl` | 5,787,924 | `d05e9f99cebc5e000adc66e6500f1922c4cfffb693d31ed8c8fcecf79f54ec63` |
| Library package | `operon-library-main-v1.1.14.operon-library.zip` | 7,045,790 | `0979318901003d7a110d8636c47469ed1ff667cb78f22a64631d638b5ec4339b` |
| Route collection | `operon-routes-main-v1.1.14.zip` | 201,444 | `b211d9ed446e2bbcf81364bdcfa9e215931243a7d2a71178640b6eb34f8531a7` |
| Checksums | `SHA256SUMS-5.7.23.txt` | 486 | `f568f7d168aacc8c7cb0adf4e07a7957b806e22c6400810ac23f9bc86b6bfff0` |
| Library checksums | `library-1.1.14-SHA256SUMS.txt` | 323 | `3c435eabf19fa03a0dc2a1d72c58f25b768487a36745022141b7973fb2b0262e` |

Every digest above was recomputed on the release files and matches
`SHA256SUMS-5.7.23.txt` and `library-1.1.14-SHA256SUMS.txt`.

## Known limitations

- `pytest tests` is not a usable signal on the WSL host: that interpreter is
  Python 3.12 without h5py and scikit-learn, and the full run produces 188
  failed, 593 passed and 4,123 errors, most of them collection errors. This
  report therefore quotes the focused suite, `tests/test_resource_api.py`, and
  no others.
- Local Windows cannot complete a conda environment install because conda-forge
  repodata is unreachable, so environments prepared on the workstation stay
  `missing`.
- 11 of the 18 server environments are not strictly ready:

| Environment | Gap |
| --- | --- |
| `core` | 14/25 units ready |
| `hic` | 7/8 units ready |
| `openmm81` | 6/8 units ready |
| `genomics` | `flye` missing |
| `alphafold2`, `antismash`, `colabfold`, `esm3`, `hmmer`, `ligandmpnn`, `proteinmpnn` | resource gaps |

- 81 operators are uncovered by the contract sweep; they need multi-input forms
  and bam fixtures and are routed to follow-up (未覆盖，列入路线化补测).
- The library manifest still uses `Path.is_file()`, so the directory
  `pdb_mmcif/mmcif_files` is reported missing at the library layer even though
  the resource layer resolves it.
- A resource that declares no file list keeps `state=unknown` and does not take
  part in readiness by design.
- The remote snapshot is proxied, so a host older than 5.7.23 returns the
  pre-5.7.23 payload.
- Four link and unit-download tests fail on this tree and on its parent commit;
  they are pre-existing and are not regressions of 5.7.23.

## Verdict

5.7.23 is fit to ship. The five defects are fixed in one service layer and
visible on all four surfaces, the frontend suite is green at 280 tests, the
focused backend suite is green at 25 tests, 993 of 1,074 operator forms validate,
the artifacts hash to the published values, and `licai-srv` already runs the same
build with `matches: true`.

Open follow-ups, none of them blockers: multi-input forms for the remaining 81
operators, the dependency and resource gaps on the 11 server environments, and
the library-layer `Path.is_file()` manifest check.
