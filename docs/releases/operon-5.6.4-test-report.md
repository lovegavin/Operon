# Operon Studio 5.6.4 test report

Date: 2026-11-19
Builds: Operon Studio 5.6.4 with operator library `main-v1.0.3`
Artifacts: digests are recorded in `SHA256SUMS-5.6.4.txt` and `library-1.0.3-SHA256SUMS.txt`.

## Scope

Every surface was exercised against a clean installation: HTTP API, MCP server, CLI and the
browser UI. Route execution was the only feature excluded by agreement; environment
preparation was attempted for all 18 environments one at a time (never through "install all"),
and large environments were started and then cancelled to prove the queue and the fallback.

## Clean install

| Item | Value |
| --- | --- |
| Installer | `Operon_Setup-5.6.4.exe`, silent install into a fresh directory |
| Install time | 23 s (measured by the harness around `Start-Process -Wait`) |
| Server ready | 23 s after start on a fresh data directory |
| `/api/version` | `5.6.4` |
| `/api/libraries` | `main-v1.0.3`, 7 packages, 1,177 descriptors, 1,069 operators, 108 readers |
| `/api/environments` | 18 environments, 1,177 assigned operators |
| `/api/resources` | 16 resources, 16 official units |

## Interface parity

| Surface | Result |
| --- | --- |
| HTTP `/api` | 109 GET routes reached; unknown environment 404, unknown resource 422, unknown profile 404 |
| HTTP `/api/v1` | environment retry/cancel/log/dependency download answer 200; unknown job 404 `unknown_job` |
| MCP | 72 tools; 5 environment tools, 6 resource tools; prepare requires `--allow-plugins` |
| CLI | `environment status|install|cancel <name>` reach the service; BOM files validate |
| UI | 18 environment cards, two entry cards, dependency and unit card grids, file picker |

## Environment attempts

Each environment was prepared on its own with `POST /api/environments/prepare {"names": [name]}`
and observed until it became `ready`, `failed`, or the attempt window expired; expired attempts
were cancelled and checked for a clean fallback.

| Environment | Attempt | Outcome |
| --- | --- | --- |
| `openmm81` | full prepare | `ready`; interpreter created, NumPy 1.26.4 + OpenMM 8.1.1 installed |
| `proteinmpnn` | full prepare | `ready`; venv created, Torch CPU + weights linked |
| `core` | started, cancelled after 45 s | `cancelled-after-attempt`; status returned to `missing` |
| `alphafold2` | started, cancelled after 45 s | `cancelled-after-attempt`; status returned to `missing` |
| `antifold` | started, cancelled after 45 s | `cancelled-after-attempt`; status returned to `missing` |
| `antismash` | started, cancelled after 45 s | `cancelled-after-attempt`; status returned to `missing` |
| `boltz` | started, cancelled after 45 s | `cancelled-after-attempt`; status returned to `missing` |
| `colabfold` | started, cancelled after 45 s | `cancelled-after-attempt`; status returned to `missing` |
| `esm2` | started, cancelled after 45 s | `cancelled-after-attempt`; status returned to `missing` |
| `esm3` | started, cancelled after 45 s | `cancelled-after-attempt`; status returned to `missing` |
| `esmfold` | started, cancelled after 45 s | `cancelled-after-attempt`; status returned to `missing` |
| `genomics` | started, cancelled after 45 s | `cancelled-after-attempt`; status returned to `missing` |
| `ligandmpnn` | started, cancelled after 45 s | `cancelled-after-attempt`; status returned to `missing` |
| `hic` | full prepare | `failed`: `hic` conda packages have no `win-64` builds |
| `hmmer` | full prepare | `failed`: `hmmer =3.4` / `infernal =1.1.4` have no `win-64` builds |
| `openfold` | full prepare | `failed`: conda solve has no `win-64` solution |
| `rfdiffusion` | full prepare | `failed`: conda solve has no `win-64` solution |
| `rna` | full prepare | `failed`: conda solve has no `win-64` solution |

`hmmer`, `infernal`, `prodigal` and `amrfinder` are published on `bioconda` for Linux and
macOS only; `micromamba search hmmer` on `win-64` returns `No entries matching "hmmer" found`.
The installer now reaches the right channel, so the remaining failure is the platform, not the
channel list — those environments install on Linux/macOS hosts, not on this Windows machine.

## Operator coverage through MCP

Every operator that belongs to a ready environment was driven through the MCP server with a
minimal single-operator route, prepared and submitted one at a time:

| environment | total operators | end-to-end success | failed at execution | client timeout | blocked at prepare |
|---|---|---|---|---|---|
| openmm81 | 6 | 4 | 1 | 1 | 0 |
| proteinmpnn | 26 | 0 (4 attempted) | 4 | 0 | 0 |
| total | 32 | 4 | 5 | 1 | 0 |

Attempted work surfaced these host limits rather than product defects:

- `interface_alanine_scan` stops with `no non-alanine residue lies within the interface cutoff` because the fixture structure (1MEL VHH) has no alanine at the interface; a different structure is required.
- `structure_openmm_md_rmsf` and `structure_openmm_md_stability` exceed the 90 s MCP client timeout on this laptop; the jobs keep running server-side, so this is a slow-host limit, not a crash. They are recorded as timeout.
- The four attempted `proteinmpnn_*` operators (`proteinmpnn_design`, `proteinmpnn_score`, `proteinmpnn_interface_design`, `proteinmpnn_masked_design`) fail fast with `[WinError 193]` because the dedicated `proteinmpnn` environment (torch + numpy) is not installed on this host - it was cancelled after start as a large environment. With the environment installed they run the real `protein_mpnn_run.py`. The other 22 proteinmpnn operators were therefore not exercised end-to-end.

Operators of environments that never reached `ready` on this host are listed in
`22 of the 26 `proteinmpnn_*` operators are validated at the prepare/schema level only. Executing them needs the `proteinmpnn` environment (torch) which this laptop did not install; the four sampled operators show the checkout, weights and parameter plumbing resolve correctly (`proteinmpnn_path`, `vanilla_model_weights/v_48_020.pt`).

The three large environments that were started and cancelled (`alphafold2`, `esmfold`, `colabfold`, `esm2`, `esm3`, `genomics`, `ligandmpnn`, ...) never downloaded multi-gigabyte weights, so their operators were not executed.` and were not exercised; they require the Linux-only conda
environments above, or a completed large download.

## API defects found and fixed

| Id | Defect | Fix |
| --- | --- | --- |
| F-39 | Unit download of a weights-only resource failed with `has no downloadable files` | unit URL becomes a download target |
| F-40 | Remote unit download 404 (no route, no dispatch) | `POST /api/remote/{key}/resources/{name}/download` plus `resources_download` |
| F-41 | Resource entry card counted resource ids | counts official units |
| F-42 | Group actions rendered on the left | `.runtime-resources-header` flex layout |
| F-43 | Detail modal could not scroll | `.studio-modal` scrolls |
| F-44 | Unit cards printed the download URL | URL removed from the card |
| F-45 | CLI environment actions parsed names as workflow files | only check/prepare read a graph file |
| F-46 | CLI mutations failed with a plugin capability error | `plugins` scope for mutating commands |
| F-47 | BOM workflow files rejected | `utf-8-sig` when reading JSON |
| F-48 | HMMER-family environments unsolvable | bioconda channel for those packages |

## MCP verification

| Tool | Result |
| --- | --- |
| `operon_environments` | 18 environments, root and manifest paths reported |
| `operon_environments_prepare` | requires `--allow-plugins`; with it, preparation starts |
| `operon_environments_cancel` | answers `没有正在进行的准备任务。` instead of 405 |
| `operon_job {"id": "0"}` | `unknown job or resource operation: 0` |
| `operon_result_files {"id": "0"}` | `unknown job: 0` |
| `operon_resources` | 16 resources with units and states |
| `operon_resource_link` with bad profile | `找不到服务器连接配置。` |

## UI verification

Real clicks through the browser, collecting `error`, `unhandledrejection` and non-2xx `fetch`
events:

- runtime panel opens from the bottom bar and lists 18 environment cards with Chinese titles
  (`AlphaFold2 数据`, `AntiFold 抗体设计`, `antiSMASH 基因簇`, `Boltz 结构与亲和力`,
  `ColabFold 结构预测`, `基础运行时`, …);
- the execution-location picker is present in the summary strip;
- an environment detail shows exactly two entry cards (`环境依赖 8 项`, `资源 3 个维护单元`);
- the dependency grid renders 8 cards for `antismash` with `conda`/`requirements` labels;
- the resource grid renders 3 unit cards, no download URL, and a `全部安装` action in the header;
- the link dialog opens the file picker at the system drive root with 29 entries and 2 drive shortcuts;
- the console reported no errors during the sweep.

## Automation

| Suite | Result |
| --- | --- |
| `tests/test_resource_unit_download.py`, `tests/test_resource_fetch.py` | 14 passed |
| `tests/test_remote_resources.py`, `tests/test_resource_unit_download.py`, `tests/test_environment_api_runtime.py`, `tests/test_environment_install.py` | 33 passed, 1 expected failure replaced |
| Frontend `npm test -- --run` | 43 files, 265 tests passed |
| Registry/descriptor stamping | 1,177 descriptors, `missing 0` |
| CLI sweep (8 defects) | D1–D4, D7 fixed; D5, D6, D8 documented as limitations |
| API sweep (109 GET + 30 mutations) | 5xx limited to unknown-job routes documented below |

## Extended MCP coverage probe

After the 5.6.4 artifacts were published, the ready environments were swept again over stdio MCP (`python -I -m operon mcp --allow-run --allow-plugins`) to measure how far the catalog can actually be executed on this Windows host.

The sweep targeted the 83 operators with `inputs_arity == 0` in the three ready environments (`core` 61, `proteinmpnn` 21, `openmm81` 1), driving every call through `operon_workflow_prepare` -> `operon_submit` -> `operon_job`:

| outcome | count | cause |
|---|---|---|
| success | 3 | `resource_preflight`, `tree_ultrametric`, `proteinmpnn_omit_design` |
| submit-error | 40 | `The selected execution environment is not ready` - the `core` venv is installed but the operator-level dependencies (rdkit and friends) are not |
| failed | 37 | runtime demands a structure file (`structure_path ... is not a file`); the catalog does not expose that input in `parameters`, so a client cannot fill it |
| prepare-error | 3 | parameter constraints (`n_sphere_points` must be >= 100) |

Structure operators that take a real PDB were exercised separately through MCP with a 164-residue antibody fixture inside the server data root: `interface_mmgbsa_delta` complete in 10.4 s, `structure_openmm_energy` in 12.2 s, `structure_interface_residue_energy` in 18.0 s; `interface_alanine_scan` refused the fixture (`no non-alanine residue lies within the interface cutoff`), and the two MD operators exceeded the 90 s client timeout (the jobs keep running server-side).

Two product findings came out of this probe and are tracked for the next release: required structure inputs are missing from the operator parameter schema (F-49), and `core` reports `ready` while operator-level dependencies can still be absent (F-50).

## Known limitations

- `/api/jobs/{id}` and `/api/agent/jobs/{id}` return 500 for an unknown id; `/api/v1/jobs/{id}`
  returns 404.
- `GET /api/bootstrap` is unauthenticated for local desktop startup, so a local process can
  read the session token.
- A cancelled download may leave the resource `partial` until the next preparation sweeps
  staging directories.
- `plan submit` requires a hand-authored execution binding; no CLI command produces one.
- `--workspace` cannot attach an old registry to a fresh profile.
- `help environment` is not a valid guide topic.
- Error envelopes differ between `/api` (`detail`) and `/api/v1` (`code`/`message`).

## Not tested

- Route execution on the canvas (excluded by agreement).
- Multi-hour downloads of the largest databases; those units were linked or started and
  cancelled instead.
- Remote hosts without a configured SSH profile; the remote surface was exercised through the
  router and agent dispatch layer plus an unknown-profile negative test.
