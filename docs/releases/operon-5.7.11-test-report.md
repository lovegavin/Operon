# Operon Studio 5.7.11 — test report

Date: 2026-11-20 (Asia/Shanghai)
Baseline commit: `9d332d86f` (5.7.10 docs) → release commit `c8b93b0d9`
Platforms: Windows 11 (clean installer), Linux `licai-srv` (`/home/<user>`)

## Scope

5.7.11 closes the MCP control-plane gap, repairs two resource-download defects
and records the Windows availability evidence for the five Linux-only
environments. The library stays at 1.1.6 with the same 1,074 operators, 108
readers and 16 resources; no operator algorithm, contract or default changed.

## Builds

| Artifact | Size (B) | SHA256 |
| --- | --- | --- |
| `Operon-Studio-v5.7.11-Windows-x64.zip` | 357,732,148 | `3dba70489f608d5e7f87549a60daa3d9336201215ba24c7f4ec4f3979df92ae8` |
| `Operon_Setup-5.7.11.exe` | 429,505,092 | `d5f2f79af45c8c17b6783e97e5063d6c5a22c397c3e8309c961b4d17b054a873` |
| `Operon-5.7.11-Server.zip` | 9,888,677 | `408fd951465c74794c0b5f3ddef07d73713a4a54cba4f96d08ce4b66a827e6d8` |
| `operon_studio-5.7.11-py3-none-any.whl` | 1,013,360 | `280822147ba60b741be9db18e49e1e7d0d2000eab0f06e4d922492469692e44c` |
| `operon_builtin_library-1.1.6-py3-none-any.whl` | 5,779,992 | `e702fb5ba8c0dd674d7cc9b26f01b07e06b4b0cabddc7540c22a10ab294f0097` |
| `operon-library-main-v1.1.6.operon-library.zip` | 7,003,732 | `f117c74ee1240d225e735d6b677ef0bb44d2fa84215d15d59265b589d863cac7` |
| `operon-routes-main-v1.1.6.zip` | 201,356 | `e26180cddf2c86a6f16c6e516221d7eae8643e975b1c87b5c2d95688c801f0ea` |

Build: mirror sync, `npm run build` (bundle `index-BQuYWwke.js`, 894,760 B),
library 1.1.6, library wheel, routes, application wheel, runtime rebuild with
the new wheel, payload and installer (3.8 minutes total).

## Clean install (Windows)

| Item | Result |
| --- | --- |
| Installer exit / duration | 0 / 24.5 s |
| Version directory | `5.7.11-b4707ef54ce7` |
| Headless server ready | 83.1 s |
| `/api/version` | `5.7.11` build `b4707ef54ce7` |
| Library | `main-v1.1.6`, 1,074 operators, 1,082 descriptors, 108 readers, 7 packages |
| Environments | 18 |
| Resources / units | 16 / 16 |

Automated acceptance: `check82.py` → 19 of 19 checks pass, no failures.

## Platform availability

The five Linux-only environments report `supported: false` with a readable
note instead of failing late in a dependency build. Evidence was produced with
the shipped micromamba binary:

```
micromamba search --platform win-64 -c conda-forge -c bioconda hmmer
micromamba search --platform win-64 -c conda-forge -c bioconda infernal
micromamba search --platform win-64 -c conda-forge -c bioconda antismash
micromamba search --platform win-64 -c conda-forge -c bioconda viennarna
micromamba search --platform win-64 -c conda-forge -c bioconda cooler
micromamba search --platform win-64 -c conda-forge -c bioconda prodigal
micromamba search --platform win-64 -c conda-forge -c bioconda samtools
micromamba search --platform win-64 -c conda-forge -c bioconda blast
```

Each query lists `win-64` successfully and returns `No entries matching "…"
found`, so the packages genuinely do not exist for Windows. The full transcript
is in `docs/verification/platform-support-5.7.11.md`.

## Resources

- `boltz` now has two real download entries (`ccd.pkl` 345,859,128 B,
  `boltz1_conf.ckpt` 3,595,352,714 B) with the mirror and upstream URLs; the
  snapshot exposes both and the planner can fetch them.
- `alphafold2` reports `official_root: afdb`, `state: partial`, 8 download
  sources and 9 expected files, so the unit can be linked from an existing
  AlphaFold database and only the missing files downloaded.
- UniRef30 tries `opendata.mmseqs.org` first and falls back to `mmseqs.com`
  (the first answers `429` for automated clients).

## MCP control plane

- Tools: **107 → 141** (+34). `frontend/src/api.ts` has 106 methods: 65 were
  already covered, 33 are added, 2 map to `operon_write_binary`, 6 are not
  applicable to an agent.
- 33 new `/api/v1` routes all authorize through `authorize(request, scope)`;
  scope behaviour verified end to end (context read-only, edit writes, plugins
  for plugin operations, `403` locally / `422`/`409` remotely when a scope is
  missing).
- `operon_environment_retry` no longer calls a missing client helper or
  duplicates the `/api` prefix, so retries return a job instead of raising.
- Installed-runtime check: `python -I -m operon mcp` lists 141 tools including
  `operon_environment_retry`, `operon_resources` and `operon_environment_log`.
- Parity tables: `docs/verification/mcp-coverage-5.7.11.md`.

## Automated checks

| Suite | Result |
| --- | --- |
| `tests/test_parity_control_plane.py` + `tests/test_mcp_server.py` | 96 passed |
| `tests/test_resource_api.py` + resource suites | 34 passed |
| Combined run (parity, MCP, resource API) | 110 passed in 13.0 s |

## Operator coverage

Every operator was attempted through the harness (Reader → Form → operator →
Form → ResultReport). The coverage snapshot and the failure buckets are in the
appendix below; failures are classified as harness data-shape gaps, environment
availability, or product defects, and the product defects found this round are
listed in the release notes.

## Known limitations

- `operon environment status <name>` still resolves the name against a workflow
  directory, not the environment root.
- Disk pre-checks estimate the expanded size and ignore inode usage.
- `pdb_mmcif` can only be mirrored with `rsync`; the HTTP mirrors do not expose
  the full tree.
- Five environments are Linux/macOS only; Windows shows a platform note.

## Not tested

- A full download of the multi-hundred-gigabyte AlphaFold databases was not
  repeated in this round; the links and per-file URLs were verified with range
  requests and the planner was exercised on smaller units.
- GPU inference paths (Boltz, OpenFold, ColabFold) were installed but not run
  on a GPU host in this round.
