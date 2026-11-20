# Operon Studio 5.7.23

5.7.23 fixes the large-resource panel and the environment badges that a field
audit of 5.7.22 found out of step with the interfaces behind them. On the audited
host every one of the 24 unit download buttons was disabled with `无缺失文件`,
13 unit cards read `未检查`, and six of the seven environments shown as `安装失败`
were short of resource files rather than of dependencies, while the one install
that really had been interrupted read `未就绪`.

The resource snapshot now publishes the per-unit download fields on the component
the panel renders, computes presence from the files each unit declares, and the
panel picks one action per state instead of disabling everything.

## Fixed

- **Downloads were never offered.** `snapshot()` published `downloadable`,
  `download_supported`, `files_present`, `files_missing` and `rsync` on the unit
  dictionary only, while each component carried `name`, `path`, `mode`, `kind`,
  `bytes`, `url`, `note`, `state`, `files`, `missing` and `size_mb`. The panel
  reads `component.downloadable`, so it always saw an empty list and disabled the
  button. `alphafold2/afdb` alone declares 9 downloadable sources.
- **Presence is decided from the declared file list.** Each unit now resolves
  `files_present` / `files_missing` from the files it declares — the unit's own
  list, or, when a resource declares exactly one manifest unit, that resource's
  `expected_files` — probing each path under the link target for a linked unit and
  under the resource root otherwise. A component's `missing`, `files_missing` and
  `files[].present` are rewritten from the same list, so a card can no longer
  report 4 missing files on the unit and 5 on the component.
- **One action per unit, six branches.** `unitAction()` decides in a fixed order:
  `pending = downloadable ∩ missing` non-empty → `下载缺失文件（n）`, enabled;
  otherwise a `rsync` source → `rsync 拉取`, enabled; otherwise
  `download_supported === false` → `无下载源`, disabled; otherwise a unit that
  declares no files at all → `未声明文件清单`, disabled; otherwise
  `missing === 0` → `已全部就绪`, disabled; otherwise
  `缺 n 个文件，没有 HTTP/rsync 源`, disabled. `pending` is empty whenever
  `missing` is empty, so a fully present unit can no longer offer to re-download
  everything.
- **`未检查` is gone.** A resource that declares no files keeps `state=unknown`,
  and its chip now reads `未声明文件清单` / `No file manifest`, followed by
  `已声明 0 项` and an empty `待补清单` plus the caption `该资源没有登记应校验的
  文件，因此不参与就绪判定`. The word `未检查` no longer appears in either
  catalog.
- **Environment badges match the cause.** Readiness is derived from `status`,
  `progress.phase` and the resource gap only: `ready` → `已就绪`;
  `incomplete` with every declared dependency installed → `资源未齐备`
  (`Resources incomplete`); `incomplete` with a missing dependency →
  `依赖缺失`; `stale` whose progress phase is `failed` → `安装已中断`
  (`Installation interrupted`); other `stale` → `需重新准备`; `missing` →
  `未安装`. The three job states (`准备安装`, `正在安装`, `安装失败`) keep their
  labels, and no two readiness labels share the same text, so the summary bar no
  longer counts a `stale` and a `missing` environment under one `未就绪`.
- **Empty reasons and duplicated dependencies.** An environment whose status has
  no `error` text falls back to a per-status sentence instead of an empty line,
  and `missingDeps` entries are normalised and de-duplicated, so
  `["wheel", "wheel"]` is reported once.
- **Environment resource counts come from the same cards.** `resource_counts()`
  counts components through `card_ready()` and attributes a resource to every
  environment in the resource's own `environments` list, so `core` reports its 5
  units instead of `resources_total=0`, and `antismash` reports 0/3 while all
  three of its cards are unready.

## Changed

- `snapshot()` in `src/web/resource_api.py`: new helpers `_declared_names`,
  `unit_declared_files`, `_split_presence`, `_card_state`, `card_ready`,
  `_merge_missing`, `_component_name` and `_mirror_components`; every component
  now always carries `downloadable`, `undownloadable`, `download_supported`,
  `rsync`, `files_present`, `files_missing`, `source` and `state`. The component
  payload only gains keys.
- `unit_coverage()` recognises a single-archive download whose file lands inside
  a declared directory, and `unit_downloads()` builds its `allowed` set from that
  coverage, so a unit whose component list is empty can still resolve its
  download source.
- `resource_counts()` in `src/web/environment_api.py` walks components instead of
  unit-level `files_missing`, and `resource_readiness()` in
  `operon/remote/server.py` takes an optional environment so the remote snapshot
  answers for one environment.
- `frontend/src/types.ts` documents `files_present`, `files_missing` and
  `source` on `LargeResourceComponent`; `frontend/src/api.ts` widens
  `EnvironmentStatus['status']` with `incomplete` and `cancelled`, both of which
  the API already returned.
- Both message catalogs hold 1118 keys in the same order; 12 keys were added and
  the retired `未检查` / `Not checked` and `无缺失文件` / `No missing files` were
  removed.

## Verification

- Repository tests, this tree: `pytest -q tests/test_resource_api.py
  tests/test_environment_resources.py tests/test_remote_resources.py
  tests/test_resource_units.py tests/test_environment_api.py
  tests/test_remote_environments.py tests/test_bridge_remote_resources.py` —
  53 passed. A wider nine-file resource run: 65 passed, 4 failed; the four
  failures reproduce on the unmodified tree and are listed in the test report.
- `tests/test_resource_api.py` gained six cases pinning the component contract:
  a component always carries the eight fields, `component.missing` equals
  `files_missing`, `files[].present` follows `missing`, and `item['missing']` is
  the union of the card gaps.
- Frontend: `npx tsc -b` clean; `npm test` (vitest) 280 passed over 43 files,
  including 14 cases in `LargeResourceSection.test.tsx`.
- i18n invariants: 1118 keys per file, equal sorted key sets, identical key
  order, equal placeholder sets, no duplicate keys and no empty values — 7/7
  PASS.
- Panel walkthrough on the installed 5.7.23 server over the same 18
  environments — see `docs/releases/operon-5.7.23-test-report.md`.

## Known limitations

- The library manifest still decides presence with `Path.is_file()`, so a
  declared directory such as `pdb_mmcif/mmcif_files` is reported missing by the
  library layer. The application layer overrides that verdict with an existence
  check and does not modify `library/seed/`; the library wheel stays at 1.1.13.
- A resource whose manifest declares no files keeps `state=unknown`. It is shown
  as `未声明文件清单` and still does not count toward readiness; the ten audited
  resources in that state need their official file lists before they can be
  verified.
- `/api/remote/{key}/resources` proxies the remote server's own snapshot, so a
  host below 5.7.23 keeps returning the old payload and its panel keeps the old
  disabled buttons.
- Four resource-link and unit-download tests fail on this tree and on the parent
  commit; they are not regressions of this release and were left unchanged.
