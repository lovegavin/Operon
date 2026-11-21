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

## Fixed in the routing layer

The same release fixes the defects that a field sweep of real
reader-to-operator routes found. Every item below was reproduced on the audited
host before it was changed, and each one now has a regression test.

- **A graph that named no labels lost the reader's own defaults.**
  `src/reader/__init__.py:read_source` passed `spec.get("labels", {})` straight
  through, so an empty mapping replaced the labels the reader declares in
  `file_input` and the axes fell back to column indices. `_declared_labels()`
  now fills only the axes the caller actually reads, and an explicit mapping
  still wins. The panel always sent the defaults, which is why the defect only
  showed up on programmatic graphs.
- **Isolated step workers had no readers.** `_run_step` starts
  `python -m operon.env_worker` with `OPERON_REGISTRY_MAINTENANCE=1` inherited,
  so the child never loaded the plugin lock and every `read_source` raised
  `No reader for extension '.pdb' … Known extensions: []`. `run_step` now writes
  the 108 reader descriptors to the step directory and the worker rebuilds them
  through `operon.plugins.register_readers`.
- **The bridge revived the wrong encoder class.** `_revive` restored encoded
  columns with `src.core.encoding.LabelEncoder` while the shipped operators
  import `operon_core.readers._encoder.LabelEncoder`, so `isinstance` was always
  false and encoded values reached the operators as strings. `_ENCODER_MODULES`
  now tries every module the library may ship, and the structure operators accept
  any encoder that offers `inverse_transform`.
- **External tools were resolved but not visible.** `find_tool` only looked at
  the managed environment roots on the application side, and
  `operon/remote/handshake.py::_response` sent a hard-coded `tools = {}`, so
  `src/web/execution_plan.py` always read an empty table. The handshake now
  publishes the resolved tools, `find_tool` looks inside
  `environments/*/bin`, and `run_step` hands the resolved tools to the bridge
  through `OPERON_PACKED_TOOLS`.
- **A bridged step had no task directory and could not be cancelled.** The
  bridge `Context` in `operon/env_worker.py` did not define `task_dir`, which
  broke `sequence_stats` on a FASTQ input. Steps now carry `task_dir`, and
  `_execute()` watches `cancel.requested` while the bridge runs, so cancelling a
  job stops the worker instead of leaving it running.
- **A dynamic output name hit the wrong data format.**
  `src/task/runner.py:check_output` indexed `data_formats.outputs` with
  `declared_outputs.index(key)`, which raised `IndexError` for an operator that
  writes its parameter-named output. `output_format_for()` reuses the last
  declared format for a dynamic name.
- **Every static port had to be registered.** `runner.check_output` required
  every name in `step.outputs` to appear in `ctx.written_outputs`, while
  `operon_sdk/protocol.py` counts a single output whenever
  `output_parameter` is set. The check now requires the parameter-named output
  and keeps the static names optional; 42 operators declare static port names
  and all 1074 declare `output_parameter`.
- **A wrapped failure hid its cause.** `operon/client.py:decode()` now appends
  `details.reason` to the message and `operon/engine/control.py` keeps the
  missing key, so a remote `KeyError` surfaces as `Unknown resource: <key>`
  instead of `The shared pool is unavailable`.
- **DSSP could not run at all.** `structure_dssp_segments` ignored its wired
  input and read `structure_path` from its own parameters, wrote crystallographic
  water into the ATOM records it handed to `mkdssp`, and `mkdssp` has no chemical
  component dictionary in its bioconda build. The operator now writes the wired
  form to a temporary PDB, skips `HOH`/`WAT`/`DOD`/`H2O`, resolves `mkdssp`
  through the environment and points `LIBCIFPP_DATA_DIR` at a `ccd` resource that
  ships the uncompressed `components.cif`. DSSP also moved out of the `genomics`
  environment into a `dssp` environment pinned at `dssp=4.4.11`, the only build
  whose `mkdssp` loads on the audited host.
- **Empty VCF summaries lost their rank.** `vcf_hardy_weinberg`,
  `vcf_site_missingness` and `vcf_sample_stats` built their tables from list
  comprehensions, so a sites-only VCF produced `np.asarray([])` (rank 1) against
  a declared rank-2 form. Empty results are reshaped to the declared width.
- **`tmm_normalize` transposed its own output.** The transform is computed on
  `[feature, sample]` but the result was rebuilt with the input's `dims`, so a
  sample-by-feature input produced a mislabelled form. The transform now returns
  its values in the input axis order.
- **Unknown feature classes failed a whole interval run.**
  `interval_annotate` and `interval_coverage` raised on any class the operator did
  not design for. `interval_table()` now decodes an unknown class as `-1`,
  reports the names through `unknown_classes` and `n_unknown_features`, and only
  raises when `strict_classes=True`.
- **A numeric chromosome column blocked the annotation operators.**
  `chr21.gff3` names its sequence `21`, so the reader keeps the column numeric
  and publishes no encoder, while `_annotation_columns.require_role('seqid')`
  insisted on one. `annotation_gaps`, `gene_structure` and the shared
  `annotation_table` now decode through an encoder when one exists and fall back
  to the value itself.
- **antiSMASH steps imported modules the environment did not install.**
  `library/seed/operon/environments.json` declared `requirements: []` for
  `antismash`, so `amrfinder_plus` failed on `No module named 'pydantic'`. The
  environment now installs `pydantic>=2.7` and `numpy`.

- **A directory archive did not count as a source.** `unit_coverage()` matched
  exact paths, base names, archive members and git prefixes, so AlphaFold 2's
  `bfd` and `pdb70` — one archive each for a whole directory — left all eleven
  files below them without a source and the panel offered no link. An entry that
  carries an archive now covers every declared file below its path, the job keeps
  that entry, and the extractor prunes the members the unit does not declare, so
  a directory archive fills exactly the files the manifest lists. The panel also
  stopped naming a protocol: a file either has a source or it does not.

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

## Added

- **Resource sources beyond HTTP.** A declared download may now be `https`,
  `http`, `ftp`, `rsync` or `git`. A git source is fetched with
  `git clone --depth 1` (optional `branch` and `subdir`); the checkout is copied
  into the resource root without its `.git` metadata, keeps executable bits and
  is rewritten when it already exists, so a read-only pack file can no longer
  block the next refresh. When the declared root is not writable the download
  falls back to `~/.local/share/operon/resources/<resource>` and logs
  `ROOT … is not writable; downloading into …` instead of failing.
- **Whole-tree archives.** A download whose `archive` is `tar`, `tar.gz`, `tgz`
  or `zip` and that declares no `member` now unpacks the entire archive below
  its target directory, file by file, with `.extract` staging, a traversal guard
  and a no-op when the target already holds data. This is what lets a host keep
  the released (unpacked) AlphaFold DB layout.
- **Dependency accounting follows the interpreter.** When a virtual environment
  sets `include-system-site-packages = true`, packages inherited from the base
  interpreter are counted, and a project declared in both `requirements` and
  `pip_wheels` is counted once. `openmm81` no longer reports `wheel` twice and
  no longer judges an inherited `wheel 0.48.0` missing.
- **CLI and MCP parity.** `operon environment install` without a name installs
  every declared environment, `operon resource unlink` reaches the DELETE route,
  and `operon environment repair` drives
  `POST /api/v1/environments/{name}/repair`. MCP now exposes 142 tools: the new
  `operon_environment_repair`, local `prepare` forwards `dependencies`, and the
  remote surface gained jobs, job status, cancel, pool status, resource cancel
  and resource log.
- **Library 1.1.14** also ships a `ccd` resource and a dedicated `dssp`
  environment, accepts numeric chromosome identifiers in `annotation_gaps`,
  `gene_structure` and `interval_annotate`, reports unknown feature classes
  instead of failing an interval run, keeps VCF summaries at their declared rank
  on a sites-only input, and returns the TMM transform in the input axis order.
- **Library 1.1.14** ships with this release: writable-first roots for ColabFold
  and Prodigal, reachable ProteinMPNN mirrors (jsdelivr, then ghproxy, then the
  upstream URL), `flye=2.9.5=py311*` for genomics, the `econml==0.16.0` and
  `lightgbm==3.3.5` pins for glibc 2.17 hosts, and the AlphaFold DB declared in
  its released layout.

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
  check; the library wheel shipped with this release is 1.1.14.
- A resource whose manifest declares no files keeps `state=unknown`. It is shown
  as `未声明文件清单` and still does not count toward readiness. Every resource
  shipped with library 1.1.14 declares its files, so the audited host has no
  resource in that state.
- `/api/remote/{key}/resources` proxies the remote server's own snapshot, so a
  host below 5.7.23 keeps returning the old payload and its panel keeps the old
  disabled buttons.
- Four resource-link and unit-download tests fail on this tree and on the parent
  commit; they are not regressions of this release and were left unchanged.
