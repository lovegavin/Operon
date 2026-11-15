# Handover — platform fixes and the minibinder design loop (2026-11-16)

Scope: the session that started from `docs/handover/2026-11-15-rc7-handover.md`. It closed
the pool admission defect, fixed five library-side operator defects, published library
0.1.20 through 0.1.22, and ran a five-round design loop (40 scored predictions plus eight
replicates) whose scores and fold-retention measurements now back both the English and the
Chinese manuscript.

## Versions and where things run

| Item | Value |
| --- | --- |
| Application (local install) | `5.1.17-rc7`, `D:\OperonTest517rc7\versions\5.1.17-f397f8157e17` |
| Operator library (local) | `main-v0.1.22`, 7 packages / 1,177 descriptors / 1,069 operators / 108 readers |
| Library releases | `operon-library-v0.1.20` (446228372), `v0.1.21` (446237964), `v0.1.22` (446279543) |
| Repository `latest` | `v5.3.0` — a collaborator application release, not this branch |
| Candidate branch | `candidate/resource-download-ui`, head `ccb4e48a` |
| Library branch | `library/resource-download-interface`, head `1fad1ee5` |
| MCP / serve | stdio wrapper `D:\OperonTest517rc7\run_mcp_legacy.cmd` (pool mode, no forced legacy) |

`paper/` is excluded from git by `/home/gavin/BioPipe/.git/info/exclude:7`, so both
manuscripts are local deliverables; everything else below is committed.

## Platform fixes

| Commit | Fix |
| --- | --- |
| `fd9731db` | the pool coordinator now reserves its own admission leases (identity compared by pid *and* creation time) |
| `75cbd795` | a quarantined attempt whose worker is proven dead and past the grace period is failed with `recovery_abandoned` and its lease released; a live worker keeps its lease |
| `1b25b2a7` | isolated workers load provider Readers and bind their parameter JSON schema |
| `69322ddc` | `publish_release.py` stops library releases from taking the repository `latest` pointer |
| `8c0f25b4` | library 0.1.20: CUDA probe follows `python_executable`, CPU runs mask devices with `CUDA_VISIBLE_DEVICES=-1`, `ca_only` parameter, `boltz_complex_confidence` cache fallback |
| `ded280af` | library 0.1.21: `fixed_positions.jsonl` keyed by the PDB stem (ProteinMPNN indexes by `b['name']`) |
| `ccb4e48a` | library 0.1.22: `antibody_developability` counts `DP` *and* `DG` isomerisation motifs |

Evidence for the lease fix: `attempt-c2644dbbce594d6e830dbeeb63c412cf` (16,662,784,204 B
lease) was quarantined for an hour with `free.ram` below the next request; after the patch
the pool reclaimed it in the first recovery pass, a job that had queued for eight minutes
was admitted 0.2 s later and finished in 3 s.

## Design loop (40 Boltz-1 scores, GPU, 20 steps each)

| Set | Seed | Mean iPTM | Median | Max | Interface pLDDT | ≥ 0.3 |
| --- | --- | --- | --- | --- | --- | --- |
| Round 1, free redesign | 1 | 0.162 | 0.096 | 0.383 | 65.3 | 2/8 |
| Round 2, interface fixed (21 sites) | 2 | 0.201 | 0.129 | 0.523 | 68.7 | 2/8 |
| Round 2 control, free, same seed | 2 | 0.225 | 0.094 | 0.868 | 72.5 | 2/8 |
| Round 3, 17 sites fixed on the 0.868 fold | 3 | 0.084 | 0.073 | 0.127 | 71.8 | 0/8 |
| Round 4, free redesign of that fold | 4 | 0.290 | 0.102 | 0.904 | 71.8 | 2/8 |

Three findings, negative-first:

1. Pinning interface positions does not raise confidence and does not preserve it. All
   eight round-3 children kept the parent's 17 interface residues and collapsed to
   0.056–0.127.
2. Free redesign of the same fold reaches 0.904 and 0.887, i.e. the fold tolerates
   wholesale sequence change; the loss is caused by the constraint pattern, not by a
   fragile backbone.
3. The upper mode is reproducible. Three repeat predictions per retained design give
   0.894 ± 0.006 and 0.851 ± 0.023, against 0.130 ± 0.025 for a low scorer, so the ≈ 0.9
   designs sit about thirty standard deviations above the low group.

Fold retention, measured by Kabsch superposition on the 193-Cα target chain: 2 of 16
children land inside 3 Å and they are exactly the two that keep their score; Pearson
r = −0.902 between iPTM and target-chain RMSD (r = −0.863 for the binder chain). The
target-chain Spearman (−0.271) is reported as unusable because the low-scoring group ties
on RMSE.

## Final candidates

Both readouts come from library 0.1.22.

| Measure | Design 3 (iPTM 0.904) | Design 4 (iPTM 0.887) |
| --- | --- | --- |
| Interface residues (≤ 5 Å) | 30 | 32 |
| Buried area | 1,180.24 Å² | 1,266.84 Å² |
| Molecular weight | 10,060.5 | 9,851.15 |
| pI | 4.531 | 4.209 |
| Net charge pH 6.0 / 7.4 | −6.65 / −7.01 | −9.68 / −10.01 |
| Hydrophobic run / fraction | 3 / 0.386 | 3 / 0.409 |
| Liabilities | N14 deamidation high, D63 isomerisation high, E1 pyroglutamate low | D14 and D63 isomerisation high |

The developability panel first reported zero isomerisation sites for both designs while
the liability scan flagged one and two `DG` motifs. The panel counted only `DP`; 0.1.22
counts both, and the re-run panels (`req-3c121a41e225827ddfbe3f0e`,
`req-5ab6e5d1086ce6e3dd90e454`) report 1 and 2 sites, agreeing with the scan site for site.

## Artifacts

| Path | Content |
| --- | --- |
| `paper/operon_bioinformatics.md` | 237 lines, Tables 1–7, no placeholders |
| `paper/operon_bioinformatics_zh.md` | 245 lines, same data and structure |
| `docs/releases/design-loop.md` | 278 lines, 64 job ids, all five scoring sets, replicate scoring, fold retention, both candidates, reproduction table |
| `docs/releases/library-0.1.22.md` | release note for the `DG` fix, with the re-run job ids |
| `scripts/design_loop/` | `collect_round.py`, `make_complexes.py`, `submit_boltz.py`, `ca_rmsd.py`, `rmsd_stats.py`, `README.md` |
| `D:\OperonTest517rc7\workspace\design_loop\` | per-round complexes, summaries, `round5/replicates.json`, `rmsd_summary.json`, final-candidate files |
| `D:\download\` | library and route bundles for 0.1.20–0.1.22 with per-version checksums |

## Blocked and open

* **Remote is unreachable.** `172.22.148.93:22` fails TCP and ICMP, and so does the
  gateway `172.22.148.1`; this is a network/VPN problem, not SSH configuration, and it has
  now persisted for three consecutive rounds. Pending on the remote side: confirm
  `managed-v1/server.json` `build_id` = `151b37f88694…`, then
  `operon_remote_ensure(profile_id="df1ff559c6fd474ca2d11a88f12a9bc7")`, re-check the
  remote `boltz` environment for `torch 2.3.1+cu121`, and re-score `s6` with the GPU.
* **No in-place library upgrade.** `operon/library_install.py:410-432` rejects a bundle
  that repeats a `library_name` under a new label, so every library bump needs remove +
  install and leaves a short window with no library. Worth a `replace` path.
* **Pool concurrency is one GPU job.** Each Boltz job reserves ~17.6 GB under
  `fixed-startup-pool`, so two need 35.2 GB against 33.4 GB of schedulable capacity; the
  eight scoring jobs therefore serialise at ~75 s each.
* **Two defects are declared, not repaired:** the remote evaluation above, and per-job CPU
  allocation (every job receives `OPERON_CPU_LIMIT` threads computed from difficulty, not
  from a GPU-aware budget).

## Picking this up

1. Start the application, confirm `main-v0.1.22` is the installed library and that the MCP
   wrapper still points at `D:\OperonTest517rc7`.
2. If the network is back: run the four remote checks in *Blocked and open* before
   touching the design loop again.
3. To extend the loop, copy `scripts/design_loop/make_complexes.py` and
   `submit_boltz.py` for the new round, then `collect_round.py` and `ca_rmsd.py`; each
   round costs about ten minutes of serial GPU time, and each replicate adds ~65 s.
