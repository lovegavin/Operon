# Operon Studio 5.6.5 test report

## Scope

Release 5.6.5 fixes the runtime status card semantics (identifier as heading,
localized name as subtitle, consistent unit count between the entry card and
the resource section), pins the detail footer, and adds a measured operator
coverage probe. The packaged library is `main-v1.0.4`.

## Build artifacts

| Artifact | Bytes | SHA256 |
| --- | --- | --- |
| `Operon-Studio-v5.6.5-Windows-x64.zip` | 357,371,785 | `eebdd115856f8c067916cfe89cbd7010cb4bc63d345913e0e17ec908f123facc` |
| `Operon_Setup-5.6.5.exe` | 429,149,141 | `d93910cc8572f00b81c5df1106111765260797741b8b0b2bc7657697662bf3aa` |
| `Operon-5.6.5-Server.zip` | 9,763,655 | `e6eb93f985bd…` |
| `operon_studio-5.6.5-py3-none-any.whl` | 993,542 | `35d8fc2c…` |
| `operon-library-main-v1.0.4.operon-library.zip` | 6,949,029 | `291f36e0…` |
| `operon-routes-main-v1.0.4.zip` | 201,313 | `5c4b24fc…` |

The authoritative hashes are in `SHA256SUMS-5.6.5.txt` and
`library-1.0.4-SHA256SUMS.txt` published next to the artifacts.

## Clean installation

| Item | Result |
| --- | --- |
| Installer | `install47.ps1`, exit 0 |
| Install root | fresh directory, version folder `5.6.5-4a60ab5f3a6d` |
| Server start | ready after 23 s on port 5793 |
| `/api/version` | `{"version":"5.6.5","build":"4a60ab5f3a6d","display":"5.6.5 (4a60ab5f)"}` |
| `/api/libraries` | `main-v1.0.4`, 7 packages, 1,177 descriptors, 1,069 operators, 108 readers |
| `/api/environments` | 18 environments, 1,177 assigned operators |
| `/api/v1/large-resources` | 16 resources, 16 official maintenance units |

## Interface checks

- `POST /api/v1/environments/{name}/retry` → 200, `POST …/cancel` → 200,
  environment returns to `missing` after cancel.
- `POST /api/v1/large-resources/{name}/download` with `unit` → 200 and a
  running operation (`phase=starting`).
- Unknown environment → 404 `unknown isolated environment: nope`; unknown
  resource → 422 `unknown_resource`; unknown remote profile → 404.
- `POST /api/browse` returns the drive roots and directory entries.
- MCP: 72 tools, `serverInfo` reports 5.6.5, `operon_environments_cancel`
  answers `没有正在进行的准备任务。`, `operon_job {"id": "0"}` answers
  `unknown job or resource operation: 0`, `operon_result_files {"id": "0"}`
  answers `unknown job: 0`.

## UI verification

The detail UI was driven through the Chrome DevTools Protocol against the
installed application on port 5793.

| Check | Result |
| --- | --- |
| Environment cards | 18 cards, each heading the identifier with the localized name underneath |
| First card | `core` with subtitle `基础运行时` |
| Entry card count | `资源5 个维护单元` matches the five unit cards in the resource section |
| Detail footer | `position: sticky`, bottom `0px`, inside the viewport |
| Link dialog | opens from a unit card, offers the file picker starting at the drive roots |
| Console errors | none collected during the probe |

## Environment preparation attempts

Every environment was prepared individually (never through a global prepare
button). Small environments were installed, large ones were started and then
cancelled to verify the fallback.

| Environment | Outcome |
| --- | --- |
| `openmm81` | ready (installed) |
| `proteinmpnn` | ready (installed) |
| `core` | ready (installed, 1,046,721,763 bytes) |
| `alphafold2`, `antifold`, `antismash`, `boltz`, `colabfold`, `esm2`, `esm3`, `esmfold`, `genomics`, `ligandmpnn` | started, cancelled after 45 s, status returned to `missing` |
| `hic`, `hmmer`, `openfold`, `rfdiffusion`, `rna` | failed |

`hic` and `hmmer` fail because their conda packages (`hmmer=3.4`,
`infernal=1.1.4`, `prodigal=2.6.3`, `ncbi-amrfinderplus=3.12`) have no
`win-64` builds: `micromamba search -c conda-forge -c bioconda hmmer` reports
`No entries matching "hmmer" found`. The channel configuration is correct, the
packages are Linux and macOS only.

## Operator coverage probe

## Operator coverage probe

Every operator was submitted through the installed MCP server with a synthesized minimal
workflow (one Reader source node plus the operator) against the clean 5.6.5 installation on
port 5793. `630` operators were attempted, `19` completed end to end and
`611` did not. The clean installation has no isolated environment
installed yet, so a submission that needs one fails before the operator body runs; that
bucket is reported separately from contract failures.

| Outcome | Operators |
| --- | --- |
| completed | 19 |
| multi-input contract | 265 |
| dependency | 233 |
| dimension contract | 61 |
| file contract | 37 |
| parameter contract | 11 |
| missing runtime input | 2 |
| other | 2 |

Completed operators: `acf`, `adf_test`, `agglomerative`, `agostino_skewness`, `agostino_test`, `anderson_darling`, `approx_entropy`, `arch_lm`, `arch_test`, `bai_perron`, `bartels_rank`, `bds_test`, `betadiver`, `bin`, `birch`, `bonett_seier`, `bootstrap_ci`, `box_pierce`, `chisq_out_test`

- **multi-input contract** (265): `alternative_polyadenylation`, `annotation_completeness`, `amrfinder_plus`, `annotation_gaps`, `allele_specific_methylation`
- **dependency** (233): `aggregate`, `adjusted_rand`, `adjusted_mutual_info`, `aldex2`, `aft`
- **dimension contract** (61): `ada_boost_regressor`, `ada_boost_classifier`, `attach_info`, `bioenv`, `bh_adjust`
- **file contract** (37): `alignment_coverage`, `alignment_insert_size`, `atac_fragment_size`, `bam_alignment_summary`, `atac_peak_call`
- **parameter contract** (11): `additive_glm`, `additive_spline_regression`, `brier_score`, `cluster_axis`, `impute`
- **missing runtime input** (2): `align_reads`, `build_contacts`
- **other** (2): `compare_groups`, `diversity`

Separate measurement on an installation where `core` and `proteinmpnn` were prepared and
`rdkit` was installed into `core`: `rdkit_qed`, `proteinmpnn_score`,
`interface_mmgbsa_delta`, `structure_openmm_energy` and
`structure_interface_residue_energy` complete end to end, which confirms that the dependency
bucket is the environment prerequisite rather than a code defect.

The probe wires a CSV source with the canonical mapping
(`{'sample': 'auto', 'feature': 'builtin'}`) and absolute fixture paths inside the configured
data root. A `CsvReader` source exposes exactly two dimensions, so operators that need more
columns, named columns or a file artifact are reported as contract limitations.


## Automation

- Backend pytest on the release tree: 112 passed, 0 failed, 1 skipped
  (`test_junction_round_trip_on_windows`, Windows-only), covering resource
  linking and fetching, unit downloads, environment install/queue/estimates,
  remote resources and the MCP installation guard.
- Frontend: 43 test files, 265 tests passed; production bundle built from the
  same sources that ship in the payload.

## Known limitations

- F-49: runtime-only inputs such as `structure_path` are absent from the
  operator parameter schema, so a generic client cannot supply them from the
  catalog alone. Affected operators are listed in the coverage table.
- F-50: an environment can report `ready` while individual operators still
  need third-party packages that are not part of the environment dependency
  list (for example `rdkit` before it was installed into `core`).
- F-51: after changing an environment's packages the shared execution pool
  keeps the previous interpreter and rejects submissions until the application
  restarts.
- F-53: the ProteinMPNN family needs the environment interpreter passed
  explicitly; the default resolution produced `[WinError 193]`.
- F-54: `CsvReader` exposes exactly two dimensions, so operators that need two
  additional columns cannot be wired from a single CSV source.
- Packages without `win-64` builds cannot be installed on Windows.

## Not tested

- Full end-to-end runs of pipelines that need multi-gigabyte reference
  databases; those units were linked or skipped by design.
- GPU-only execution paths.
