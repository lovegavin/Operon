# Operon Studio 5.7.16 — test report

## Scope

5.7.16 follows 5.7.15 (dependency counts on remote snapshots, installer
actions) and closes the defects reported against it:

| ID | Defect | Fix |
| --- | --- | --- |
| F-112 | Operators that produce files failed with `missing file for role ...envbridge-<id>/...`: the bridge copied artifacts into a temporary directory that was deleted before the artifact was validated. | `operon/environments.py` relocates produced files into `OPERON_ARTIFACTS_DIR` (or `.operon-artifacts/`) before building the `FileArtifact`, and recomputes fingerprints. |
| F-113 | `find_tool()` never looked into the declared environment's `bin`, and `probe()` returned before validating the environment, so external tools were reported as "not on PATH" even when installed. | `find_tool(name, environment)` also searches `environments/<name>`, `bin`, `Scripts` and nested `envs/*`; `probe()` now fails fast with "isolated environment '<env>' is not installed". |
| F-114 | `core` declared no scientific stack although most operators route to it; `hic` missed `psutil`. | `core` requirements now include pandas, scipy, scikit-learn, statsmodels, matplotlib, seaborn, h5py, openpyxl and biopython (19 entries); `hic` gained `psutil`. |
| F-115 | An environment with an interpreter but missing packages was shown as *ready*; the reported error text was cleared; the dependency button was refused unless the environment was already ready, and the panel never showed why. | `state()` reports `incomplete` with `missing_dependencies` and a readable error; the unconditional error reset is gone; dependency install accepts `ready` and `incomplete` and otherwise starts the environment first. |

## Builds

| Artifact | Bytes | SHA256 |
| --- | --- | --- |
| `Operon-Studio-v5.7.16-Windows-x64.zip` | 357,802,188 | `fb77eebb1b2048e833c7b29d031e6c9e63d10196f5e2346b0076a282a257cdf3` |
| `Operon_Setup-5.7.16.exe` | 429,579,553 | `a68a1b61692f741acc6dfc9a948573000b8eecc21f974777008e6e4f096697e8` |
| `Operon-5.7.16-Server.zip` | 9,917,801 | `aa2dd722b2fa785794d69dd66e3443a81497e53489bc2b40e5466e2b85a6b444` |
| `operon_studio-5.7.16-py3-none-any.whl` | 1,017,240 | `568ad8b6bbb3d4a75cb91666ee38490437da3820055a760ee1b31b500ea6fcbc` |
| `operon_builtin_library-1.1.10-py3-none-any.whl` | 5,783,237 | `b0e61dc3f1ef8d31154eb417e3c230497d095a895075a8ba601f19b392a91677` |
| `operon-library-main-v1.1.10.operon-library.zip` | 7,019,844 | `113d3559104a63276dcdf80ba5983205a27e6c2826e52502cfa3d52987daa21f` |
| `operon-routes-main-v1.1.10.zip` | 201,521 | `8b2cc51b4b847148dd923b472666ef838f8df0c2aa1a0b9975a725974d2de184` |

## Clean install

| Check | Result |
| --- | --- |
| Installer exit code | 0 |
| Installation time | 19.3 s |
| Version directory | `5.7.16-1813f6379fa8` |
| `/api/version` | 5.7.16 |
| Library | `main-v1.1.10`, 1,074 operators, 1,182 descriptors, 7 packages, 108 readers |
| Environments | 18 (5 gated on Windows, `platform_note` in Chinese) |
| MCP tools | 141 |

## Five states

`/api/environments` exposes `dependency_total`, `dependency_installed`,
`missing_dependencies`, `resources_total`, `resources_ready`,
`resources_missing`, `shared_resources_total` and `shared_resources_ready`.
The panel derives `ready | not-ready | queued | installing | failed` from
those fields, and the bundle only contains the five labels.

## Installer actions (clean install)

| Action | Expected | Observed |
| --- | --- | --- |
| Install environment | 200 with job | 200, job `3fc36f78cca1487e9aed4b8ccf308815` (0.86 s) |
| Cancel | 200, environment falls back within a few seconds | 200, `cancelled=true`, 0.77 s |
| Retry | 200 | 200 (0.72 s) |
| Install dependency on a not-ready environment | 200 with job (creates the environment first) | 200, job `af69717bef524e7a807e53bc8a5e587e`, queued (0.56 s) |
| Download a resource unit | 200, operation reaches a terminal state | 200, `succeeded`, 30,099,493 B |
| Read the environment log | 200 with real text | 200, 71 characters (placeholder for an environment that never ran) |

## Operator coverage

Linux (srv, 5.7.14 + library 1.1.8, private instance) after the `core`
scientific stack was installed:

| Metric | Value |
| --- | --- |
| Operators attempted | 311 of 1,074 |
| Completed | 141 (45.3 % of attempted) |
| Environment bucket | 23 (was 169 before the `core` fix) |
| Missing pandas / scipy / statsmodels / scikit-learn | 0 / 0 / 0 / 0 |

Remaining Linux failures are dominated by other categories: `other` 90,
`contract` 29, `column` 12, `external_tool` 7, `shape` 6.

## Automated checks

- `tests/test_environment_artifacts.py`, `tests/test_dependency_probe.py`,
  `tests/test_environment_dependencies.py`, `tests/test_environment_readiness.py`
  — 10 passed.
- Frontend: 43 files / 265 tests passed; `tsc -b` clean.

## Known limitations

- Five environments declare Linux-only packages; on Windows they stay *not
  ready* with a platform note and cannot be installed.
- A fresh environment is *not ready* until it is installed explicitly — this is
  intentional (`dependency_policy: explicit-route-preparation`).
- Contract errors from the compiler mix Chinese and English messages.

## Not tested

- Full 1,074 operator sweep on Linux after this build (the 311/141 numbers come
  from 5.7.14 + library 1.1.8).
- Real GPU-only paths (no CUDA host available).
