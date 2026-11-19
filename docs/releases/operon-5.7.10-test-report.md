# Operon Studio 5.7.10 test report

Scope: six-state readiness, durable environment logs, queued dependency installs, the
`result_report` operator, MCP/CLI parity, and the installer robustness fixes
(F-95 through F-102).

## Artifacts

| File | Bytes | SHA-256 |
|---|---|---|
| Operon-Studio-v5.7.10-Windows-x64.zip | 357678184 | dce993f2545cf1c33ea04889b796fcb0314bc17cd4633518250aad10de89ca50 |
| Operon_Setup-5.7.10.exe | 429451126 | 9a0b747ebfabec0da492d9013a4b4917f5576f7951ec44365b27c5f90cc3265f |
| Operon-5.7.10-Server.zip | pending | a5759b943fa6c040dc6743ead851df878d775b366fa87e7c39c7ffc1ccf58661 |
| operon_studio-5.7.10-py3-none-any.whl | 1008260 | e869bdb75a188c2f4cc34ef8b4da43238bd41f3757e3f9fd25466b179b8e672f |
| operon_builtin_library-1.1.5-py3-none-any.whl | 5779952 | 7d6a2e194ef4044d66893aaea1ffabd4ed8da428af1cf0f48af256c09d809026 |
| operon-library-main-v1.1.5.operon-library.zip | 7003471 | ff068fb234658019b566f9610b725746ee717468d827a420e66a413e525485b5 |
| operon-routes-main-v1.1.5.zip | 201330 | fd9d383d3fb0e7965e441d4de1a6f1fa6fd37b1be145248936c4e426af5f1475 |

`SHA256SUMS-5.7.10.txt` and `library-1.1.5-SHA256SUMS.txt` in the same directory carry the same digests.

## Clean install

| Check | Result |
|---|---|
| Installer | exit 0, ready after 38 s |
| Version | `5.7.10 (a73bf963)` |
| Environments | 18 |
| Library | `main-v1.1.5`, 1,074 operators (includes `result_report`) |
| MCP tools | 107 |
| Diagnostics | `result_report` appears in `operon_operator_search`; environment log returns the persisted text or the synthetic fallback |

## Environment matrix

Windows (this host): 13 environments install to `ready`
(`core`, `openmm81`, `ligandmpnn`, `esmfold`, `rfdiffusion`, `proteinmpnn`, `esm2`,
`boltz`, `antifold`, `esm3`, `alphafold2`, `colabfold`, `openfold`). Five environments
are gated by the platform list because their command line dependencies have no
win-64 builds and the prepare call fails in about two seconds with a readable reason:
`antismash`, `genomics`, `hic`, `hmmer`, `rna`.

Linux (licai-srv): all 18 environments reach `ready`. The last batch covered
`esm3` 12.66 GB, `esmfold` 12.18 GB, `openfold` 11.85 GB, `antifold` 12.52 GB,
`proteinmpnn` 11.75 GB, `hic` 6.91 GB, `colabfold` 9.39 GB, `genomics` 8.99 GB.
`esmfold` needed two retries because a silent transfer stalled past the 60 s
watchdog; the retry succeeded from the pip cache. Shebang rewriting was verified in
`esmfold/bin` after promotion.

## Reader-first coverage

The reader-first harness submits a graph of `Reader -> operator -> result_report` and
requires a report artifact before counting a line as complete. `filter_min` completes
with an ordered chain `['op', 'report']` and a non-empty report, which proves the data
model. The sweep over all 1,074 operators is still in progress: the reader stage is
solved, and the remaining failures are data shaping issues inside individual
operators (a class column with a single class, an unnamed dimension that must be
`value`, categorical names outside the predictors). No line is counted as passing
until it produces a report.

For reference, the earlier direct-form sweep attempted all 1,073 operators and
finished 231 with 842 failures; the buckets were contract shape 417, column 154,
file input 104, shape 91, parameter 44, environment 25, dependency 7. Those numbers
are recorded here because they set the order in which the families are being fixed.

## Automated checks

- `tests/test_result_report.py`: 2 passed
- `tests/test_environment_promote.py` and `tests/test_environment_install_lock.py`: 5 passed
- `tests/test_parity_control_plane.py`: 58 passed
- server/CLI/pool/viewer/transport suites: 98 passed
- remote bridge and environment API suites: 18 passed
- frontend: 43 files, 265 tests passed

## Known limitations

- Five environments stay unavailable on Windows by design, with a readable reason.
- `esmfold` can lose a retry when a package transfer stalls longer than 60 s.
- Reader-first coverage is incomplete for operators that need domain fixtures
  (single-class classification, fixed dimension names, image inputs).
- A few desktop-only endpoints (preferences, plugins beyond list/install, route
  collections, workflow import, remote refresh) have no MCP/CLI wrapper yet.

## Not tested

- No full rerun of the 4,500 s backend suite for this release.
- No end-to-end MCP session against the remote host for every new tool.
