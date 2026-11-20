# Operon Studio 5.7.17 test report

## Scope

This release fixes four defects found while running the operator sweep on Linux
and adds two maintenance interfaces. It changes the installer, the resource link
step and the default `core` dependency list; the operator inventory stays at
1,074 operators in 7 packages.

## Defects fixed

| ID | Symptom | Fix |
| --- | --- | --- |
| F-116 | Linking an existing resource directory returned 409 `target holds existing data; remove it explicitly`, so a partially populated directory could not be completed | `resource_link` merges when `replace` is set on a non-managed tree: only declared files missing from the target are linked, existing files stay untouched, receipt records `linked_files` |
| F-117 | Every environment installation failed with `invalid choice: 'raw'` because the bootstrapped pip rejects `--progress-bar raw` | installer requests `--progress-bar on` |
| F-118 | Entry-point scripts kept `.staging-*` shebangs after promotion, so tools such as `antismash` could not execute; rewriting only walked one level and skipped installed trees | `_rewrite_shebangs` recurses and repairs existing environments; new `repair()` and `POST /api/environments/{name}/repair` |
| F-119 | Environments that were never created reported no dependency information | `state()` always fills `dependency_total`/`dependency_installed`/`missing_dependencies` |

## Default runtime dependencies

The `core` runtime now declares the analysis packages that core-scoped
operators import: `networkx`, `rdkit`, `lifelines`, `anndata`, `arch`,
`econml`, in addition to `pandas`, `scipy`, `scikit-learn`, `statsmodels`,
`matplotlib`, `seaborn`, `h5py`, `openpyxl` and `biopython`. A clean install
therefore reports 25 declared dependencies for `core` instead of 19.

## Interfaces

- `POST /api/environments/{name}/repair` (and `/api/v1/...`): rewrites stale
  staging shebangs of an installed environment and returns the refreshed
  environment snapshot plus `repair: {name, directory, rewritten}`.
- `POST /api/v1/large-resources/{name}/link` with `unit` and `replace` on a
  partially populated tree: returns `status: "merged"` and `linked_files`.

## Builds

| Asset | Bytes | SHA256 |
| --- | ---: | --- |
| Operon-Studio-v5.7.17-Windows-x64.zip | 357,809,948 | b81343a5e91e8f96dd438eb7e27d2732501d2c9637a969b4aedda3ca706b28fd |
| Operon_Setup-5.7.17.exe | 429,587,315 | 68055879682d10254f40b68bbe62074cf8f8f666146bb1b0d66a457f4b06a543 |
| Operon-5.7.17-Server.zip | 9,921,895 | 3bb7a468a3ccd97c08a5062c85fbd3c538f7d67979ba65a50ca25749d9c63a8e |
| operon_studio-5.7.17-py3-none-any.whl | 1,017,446 | b20e68cb78e6883fcad6994291983b3211e0af8b3c1e898601567168d2a7cd42 |
| operon_builtin_library-1.1.11-py3-none-any.whl | 5,783,580 | b09c523b797570175ba94b32c3ab2cdfa705bfc487d369a2e00c052cd5d465bc |
| operon-library-main-v1.1.11.operon-library.zip | 7,022,059 | 3e01b91bf8fc036924abe1ae8c5fd3d1730c54b93ea3088fae11d25c39f8ea6f |
| operon-routes-main-v1.1.11.zip | 201,449 | 545d62f7b0f5c9cbd9b496e436797e70579943763da5c4dc4de431ffdb37d69e |
| SHA256SUMS-5.7.17.txt | 712 | f3f9fc6fe697efcf9c5738e699780e000a8afbda3fbc64295a343a784c912567 |
| library-1.1.11-SHA256SUMS.txt | 210 | abdad2f24742e3f86cb632a7ab3624d378fa7db93bd1cea83cb69e2654fe19db |

The payload ships `frontend/assets/index-BhlUizHT.js` (896,966 B) and both
release documents, and records `source_commit=e55354d30cab2cdf2c6ab79806077c2a613cb30b`.

## Automated checks

- `tests/test_environment_install.py`: 21 passed (includes the two new repair
  tests and the dependency-aware readiness assertions).
- `tests/test_resource_link.py`: 29 passed, 1 skipped (merge, refusal and
  managed-replacement cases).
- `tests/test_environment_readiness.py`, `tests/test_environment_dependencies.py`,
  `tests/test_environment_artifacts.py`, `tests/test_dependency_probe.py`:
  10 passed.

## Clean installation

| Item | Result |
| --- | --- |
| installer | exit 0, 18.3 s, version directory `5.7.17-d6de579dd9eb` |
| headless server | ready after 60.9 s on port 5839 |
| `/api/version` | `5.7.17 (d6de579d)` |
| library | `main-v1.1.11`, 1,074 operators, 1,182 descriptors, 7 packages, 108 readers |
| environments | 18 entries, five platform-gated entries report `supported=false` with a Chinese note |
| `core` dependencies | `dependency_total=25`, `installed=0`, `status=missing` on a fresh install |
| resources | `alphafold2` reports `official_root=afdb`, `state=partial`, `downloads=8`, `expected_files=9` |
| MCP | 141 tools, `serverInfo {"name":"Operon","version":"5.7.17"}` |
| installer actions | install/cancel/retry/dependency/download/log all answer: prepare 200, cancel 200 (`cancelled=True`, 2.1 s), retry 200, dependency 200 (queued job `8b8e4142…`), esm2 download `succeeded` 30,099,493 B, log 200 |
| repair | `POST /api/v1/environments/openmm81/repair` 200 with `repair.rewritten=0`; unknown environment 404 |

All nine assets were re-verified on disk and match the SHA256 sums
(`mismatch=0`), and the checksum files validate with `sha256sum -c`.

## Coverage follow-up (fixture-driven round)

A contract-aware fixture pass re-ran 172 operators that had never completed
(they accounted for 170 recorded failures plus two duplicates on the server
side). 63 of them completed for the first time, which lifts the measured total
from 419 to **482 of 1,074 operators (44.9%)**.

What changed in the fixtures, not in the product: protein operators now receive
protein alphabets, single-sequence operators receive one record, MSA inputs are
equal length, CDS inputs are valid and in frame, tabular inputs use the column
names the contracts request, and numeric/enumerated/boolean parameters follow
their schema. Those four classes alone accounted for roughly 57 of the previous
failures.

Remaining 109 failures in this round, by cause:

| Group | Count |
| --- | ---: |
| Environment reported not ready (submit 409) | 26 |
| Missing Python dependency in the target environment | 9 |
| External tool missing or not executable | 9 |
| Fixture: table shape | 3 |
| Fixture: parameter values | 14 |
| Fixture: sequence count, length or window | 5 |
| Fixture: sequence content or thresholds | 2 |
| Fixture: column names or labels | 14 |
| Fixture: data content, samples or grouping | 18 |
| Fixture: fixture file missing (sam, bam, cool) | 4 |
| Fixture or contract (multi-input, representation conversion) | 2 |
| Suspected product defect | 3 |

Suspected product defects found by this round:

1. A batch of operators submits with `environment_not_ready` while the same
   environment reports ready in `/api/environments`; `crispr_array_detect`
   completed in the same round, so the readiness fingerprint and the actual
   environment disagree for at least 26 operators.
2. Target environments lack base dependencies (`Bio`, `numpy`, `econml`,
   `torch`) even though their operators import them.
3. External tools are either absent or unusable from the declared environment:
   `run_alphafold.py`, `jackhmmer`, `hhblits`, `antismash`, `tRNAscan-SE`
   (missing Perl library), `QUAST`, `AMRFinderPlus`, `colabfold_batch`, and a
   ProteinMPNN path check that rejects a data file with an unrelated message.
4. `pairwise_alignment` rejects both three and two sequences per side with the
   same assertion, so the contract cannot be satisfied.
5. `variant_consequence` raises a bare `KeyError` (`'chr1'`) without wrapping
   the message or normalising chromosome names.
6. `prodigal_genes` executes the value of `prodigal_path` without checking that
   it is executable, surfacing `[Errno 13] Permission denied` for a data file.

## Known limitations

- Operators that need `torch`, `biotite` or a GPU runtime still have to be run
  inside the environment that ships those packages; `core` intentionally keeps
  the lighter analysis stack only.
- The resource sweep on Linux is still in progress: 419 of 1,074 operators have
  completed at least once. Remaining failures are dominated by per-operator
  fixture shapes rather than installer defects.

## Not tested

- Full re-installation of all 18 environments on Linux after this release.
- GPU environments on hardware without a GPU.
