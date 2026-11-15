# Handover — platform fixes and the minibinder design loop (2026-11-16)

Scope: the session that started from `docs/handover/2026-11-15-rc7-handover.md`. It closed
the pool admission defect, fixed four library-side operator defects, published library
0.1.20 and 0.1.21, and ran a four-round design loop whose scores and fold-retention
measurements now back both the English and the Chinese manuscript.

## Versions and where things run

| Item | Value |
| --- | --- |
| Application (local install) | `5.1.17-rc7`, `D:\OperonTest517rc7\versions\5.1.17-f397f8157e17` |
| Operator library (local) | `main-v0.1.21`, 7 packages / 1,177 descriptors / 1,069 operators / 108 readers |
| Library releases | `operon-library-v0.1.20` (446228372), `operon-library-v0.1.21` (446237964) |
| Repository `latest` | `v5.3.0` — a collaborator application release, not this branch |
| Candidate branch | `candidate/resource-download-ui`, head `c90d1505` |
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

Two findings, both negative-first:

1. Pinning interface positions does not raise confidence and does not preserve it. All
   eight round-3 children kept the parent's 17 interface residues and collapsed to
   0.056–0.127.
2. Free redesign of the same fold reaches 0.904 and 0.887, i.e. the fold tolerates
   wholesale sequence change; the loss is caused by the constraint pattern, not by a
   fragile backbone.

Fold retention, measured by Kabsch superposition on the 193-Cα target chain: 2 of 16
children land inside 3 Å and they are exactly the two that keep their score; Pearson
r = −0.902 between iPTM and target-chain RMSD (r = −0.863 for the binder chain). The
target-chain Spearman (−0.271) is reported as unusable because the low-scoring group ties
on RMSE.

Final candidate readout (`Round 4` design 3): 30 interface residues within 5 Å,
1,180 Å² buried, pI 4.53, net charge −6.65 at pH 6.0 / −7.01 at pH 7.4, three liabilities
(N14 deamidation high, D63 isomerisation high, E1 pyroglutamate low). The developability
panel reports zero isomerisation motifs where the liability scan flags D63 — kept as a
disagreement rather than reconciled.

## Artifacts

| Path | Content |
| --- | --- |
| `paper/operon_bioinformatics.md` | 227 lines, Tables 1–6, no placeholders |
| `paper/operon_bioinformatics_zh.md` | 235 lines, same data and structure |
| `docs/releases/design-loop.md` | 233 lines, 51 job ids, all five scoring sets, fold retention, candidate readout, reproduction table |
| `scripts/design_loop/` | `collect_round.py`, `make_complexes.py`, `submit_boltz.py`, `ca_rmsd.py`, `rmsd_stats.py`, `README.md` |
| `D:\OperonTest517rc7\workspace\design_loop\` | per-round complexes, summaries, `rmsd_summary.json`, final-candidate files |

## Blocked and open

* **Remote is unreachable.** `172.22.148.93:22` fails TCP and ICMP, and so does the
  gateway `172.22.148.1`; this is a network/VPN problem, not SSH configuration. Pending on
  the remote side: confirm `managed-v1/server.json` `build_id` = `151b37f88694…`, then
  `operon_remote_ensure(profile_id="df1ff559c6fd474ca2d11a88f12a9bc7")`, re-check the
  remote `boltz` environment for `torch 2.3.1+cu121`, and re-score `s6` with the GPU.
* **No in-place library upgrade.** `operon/library_install.py:410-432` rejects a bundle
  that repeats a `library_name` under a new label, so 0.1.20 → 0.1.21 required remove +
  install and left a short window with no library. Worth a `replace` path.
* **Pool concurrency is one GPU job.** Each Boltz job reserves ~17.6 GB under
  `fixed-startup-pool`, so two need 35.2 GB against 33.4 GB of schedulable capacity; the
  eight scoring jobs therefore serialise at ~75 s each.
* `D:\OperonTest517rc7` still holds the one-off patch and inspection scripts; the five
  scripts worth keeping are already in `scripts/design_loop/`.

## Picking this up

1. Start the application, confirm `main-v0.1.21` is the installed library and that the MCP
   wrapper still points at `D:\OperonTest517rc7`.
2. If the network is back: run the four remote checks in *Blocked and open* before
   touching the design loop again.
3. To extend the loop, copy `scripts/design_loop/make_complexes.py` and
   `submit_boltz.py` for the new round, then `collect_round.py` and `ca_rmsd.py`; each
   round costs about ten minutes of serial GPU time.
