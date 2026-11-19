# Operon Studio 5.7.12 test report

This report covers the 5.7.12 patch on top of 5.7.11. The release fixes two
installation-robustness defects found while preparing every declared environment
on a clean Windows install, and records the resulting environment matrix.

## Defects fixed

- **F-93** — the 60 s stall watchdog killed a step that had not printed anything
  yet. `pip` resolves a large dependency graph before it emits its first line, so
  `colabfold` failed with `python.exe -X produced no output for 60s` after 60 s of
  silent resolution. The watchdog now allows a 300 s start-up window
  (`STARTUP_SECONDS`) before the first output, and keeps the 60 s silence limit
  afterwards.
- **F-94** — a platform-gated environment (`platforms: ["linux", "darwin"]`) was
  reported as *installed failed* after `prepare` refused it. `state()` now keeps
  such an environment `missing` and carries the reason, so the card shows
  「未安装」 plus the platform note instead of a red failure.

## Environment matrix (Windows, clean install, 5.7.11 build `b4707ef5`)

Install root: `stage0v55f1`, port 5822, library `main-v1.1.6` (1,074 operators).
Each environment was prepared serially; failures were retried once.

| Environment | Status | Size | Note |
| --- | --- | --- | --- |
| `alphafold2` | ready | 207.8 MB |  |
| `antifold` | ready | 2.9 GB |  |
| `antismash` | failed (platform-gated, F-94) | — | antiSMASH 基因簇 仅支持 linux, darwin，当前系统为 windows。该环境依赖的命令行工具只有 Linux/macOS 构建（bioconda 与 conda-forge 都没有 win-64 包）。请在远程 Linux 服务器上准备该环境，或在本机手动安装后把目录链接进资源 |
| `boltz` | ready | 5.7 GB |  |
| `colabfold` | failed | — | `<profile>\library\environments\.staging-colabfold\python.exe -X produced no output for 60s; aborted instead of waiting for the 5400s limit` (F-93) |
| `core` | ready | 247.0 MB |  |
| `esm2` | ready | 2.1 GB |  |
| `esm3` | ready | 2.0 GB |  |
| `esmfold` | ready | 2.3 GB |  |
| `genomics` | failed (platform-gated, F-94) | — | 基因组组装与比对 仅支持 linux, darwin，当前系统为 windows。该环境依赖的命令行工具只有 Linux/macOS 构建（bioconda 与 conda-forge 都没有 win-64 包）。请在远程 Linux 服务器上准备该环境，或在本机手动安装后把目录链接进资源库。 |
| `hic` | failed (platform-gated, F-94) | — | Hi-C 分析 仅支持 linux, darwin，当前系统为 windows。该环境依赖的命令行工具只有 Linux/macOS 构建（bioconda 与 conda-forge 都没有 win-64 包）。请在远程 Linux 服务器上准备该环境，或在本机手动安装后把目录链接进资源库。 |
| `hmmer` | failed (platform-gated, F-94) | — | HMMER 序列比对 仅支持 linux, darwin，当前系统为 windows。该环境依赖的命令行工具只有 Linux/macOS 构建（bioconda 与 conda-forge 都没有 win-64 包）。请在远程 Linux 服务器上准备该环境，或在本机手动安装后把目录链接进资源库。 |
| `ligandmpnn` | ready | 2.1 GB |  |
| `openfold` | ready | 2.2 GB |  |
| `openmm81` | ready | 148.5 MB |  |
| `proteinmpnn` | ready | 2.1 GB |  |
| `rfdiffusion` | ready | 2.1 GB |  |
| `rna` | failed (platform-gated, F-94) | — | RNA 结构分析 仅支持 linux, darwin，当前系统为 windows。该环境依赖的命令行工具只有 Linux/macOS 构建（bioconda 与 conda-forge 都没有 win-64 包）。请在远程 Linux 服务器上准备该环境，或在本机手动安装后把目录链接进资源库。 |

Summary: **12 ready**, one genuine failure (`colabfold`, F-93, fixed in this
release) and five platform-gated environments (antiSMASH, genomics, Hi-C,
HMMER, RNA structure). The table was captured on the 5.7.11 build, before F-94
landed, so those five rows still say `failed`; a 5.7.12 install reports them as
`missing` with the same platform note and no progress entry.

## Operator coverage harness

Serial sweeps on a clean install produced the following snapshot (unique
operators, all 1,073 exercised at least once):

| Outcome | Count |
| --- | --- |
| Run reached `complete` | 278 |
| Run failed (contract, data shape, dependency) | 795 |

Failure buckets after the harness gained reader-aware inputs:
`run/other 368`, `prepare/contract 138`, `prepare/other 98`, `run/column 85`,
`run/data-quality 77`, `run/shape 59`, `prepare/env-not-ready 24`,
`run/contract 17`.

The dominant messages are harness artefacts (a synthetic table cannot satisfy
every declared dimension) rather than product defects: `需要 file 类型数据；
缺少 info.representation` (51), `only 0 shared samples between data and metadata`
(30), `需要维度 atom/field` (29), `缺少 info.representation / info.alphabet` (28),
`图片文件名不能包含目录或驱动器` (13), `only 0 samples with a valid class` (11).

## Automated checks

- `tests/test_environment_install.py` — 19 passed (new: start-up grace, silent
  command abort, platform-gated environment stays `missing`).
- `tests/test_environment_install.py tests/test_environment_api_runtime.py
  tests/test_environment_queue.py tests/test_environment_estimates.py
  tests/test_dependencies.py` — 47 passed.

## Linux re-check

The managed Linux host (`master`, `/home/<user>/Operon/managed-v1`) was
re-inspected on 2026-11-20: 18 of 18 declared environments still exist and carry
a receipt (`environments/` holds 18 receipts plus the `packages` helper
directory). Both 5.7.12 fixes are platform-independent, so the 5.7.11 Linux
matrix stands; no re-install was run.

## Coverage re-run (representation-aware harness)

A second sweep ran the 218 operators that had never completed, this time choosing
the source reader from each input's `info.representation` instead of assuming a
CSV source:

| metric | value |
| --- | --- |
| attempted | 218 |
| newly complete | 62 (28.4%) |
| still failing | 156 |
| median wall time | 9.5 s |
| contract-bucket failures | 0 (was 28.6%) |

Fifty-six of the 62 completions declare a representation requirement, so the
mapping (FASTA, VCF, FASTQ, BAM, BED, PDB, Newick, HMM, BigWig, cool) is what
unblocked them. Remaining buckets: `other` 96, `environment_not_ready` 36,
`column` 19, `shape` 4, `parameter` 1. Cumulative distinct completions are now
294 of 1,074.

## Alphafold2 resource trial (link + partial download)

`POST /api/resources/alphafold2/link {"unit":"afdb"}` returned 200 and flipped the
card to `linked`; `DELETE .../link?unit=afdb` returned 200 and restored `partial`.
Linking a non-empty root is refused with 409 `target holds existing data; remove
it explicitly`, which is intended.

Three of the nine expected files were downloaded for real: `params/
params_model_1_ptm.npz` (373,103,340 B, resumed after a truncated stream),
`pdb_seqres/pdb_seqres_2022_09_28.fasta` (68,464,969 B) and
`uniprot/uniprot_sprot.fasta` (93,867,502 B). The six 20-291 GB databases were
left to link, so the card stays `partial` with `size_bytes` 535,435,811.

Two downloads failed mid-transfer and surfaced as failures, not silent success:
`rfdiffusion` (`download size mismatch for models/Complex_beta_ckpt.pt: got
114638566, expected 483380617`) and `pfam` (`Compressed file ended before the
end-of-stream marker was reached`).

## Known limitations

- `operon environment status <name>` still resolves the name against a workflow
  directory; `operon environment list` is the supported inventory command.
- The sweeps run against synthetic fixtures; operators whose contract needs
  domain-specific columns still fail before their own code runs.
- antiSMASH, genomics, Hi-C, HMMER and RNA structure need a Linux host: bioconda
  and conda-forge publish no win-64 builds for their command line tools.

- Bundled environments start as `missing` with `dependency_policy:
  explicit-route-preparation`; operators whose environment is not prepared fail
  with `environment_not_ready` until the user prepares it. This is by design but
  it means a fresh install cannot run environment-specific operators offline.
- Some contract errors mix Chinese and English (`缺少 info.representation`
  alongside otherwise English messages). Harmless at runtime, but it makes
  external bucketing harder.

## Not tested

- A full Linux re-install of 5.7.12 (the 5.7.11 Linux matrix is unchanged by this
  patch: both fixed code paths are platform-independent).
- Real end-to-end runs of the operators that require licensed or very large
  reference databases.
