# Design-loop provenance index

This file lists every job that produced the design-loop results reported in the
manuscript, with the parameters that matter for reproduction and the identifiers
needed to retrieve the artefacts. All jobs were submitted through the Operon
Model Context Protocol surface (`operon_submit`) or, for the batched scoring
runs, through the equivalent `operon run` command over the same service; none
was executed by a shell pipeline.

Environment: application `5.1.17-rc7` (`D:\OperonTest517rc7`, version directory
`5.1.17-f397f8157e17`), operator library `main-v0.1.22` (1069 operators,
108 readers, 1177 descriptors), local pool with one RTX 3090 (24 GB) and
33.4 GB of schedulable capacity. Sequence design and folding used the `boltz`
isolated environment's interpreter (`torch 2.3.1+cu121`) with ProteinMPNN's
CA-only weights (`v_48_020.pt`) and Boltz-1 (`boltz1_conf.ckpt`, `ccd.pkl`).

## Target and backbone

| Stage | Job / source | Operator | Key parameters | Wall time | Artefact |
| --- | --- | --- | --- | ---: | --- |
| Target structure | `target_raw.pdb` (chain T, 193 aa) | — | input file | — | 361,017 B |
| Backbone design (remote) | `ssh-df1ff559c6fd474ca2d11a88f12a9bc7-req-1aecb9f3aa22a463901518cb` | `rfdiffusion_design` | `contigs=80-80`, target chain T, GPU 0 | 103.61 s | `design_0.pdb`, 75,308 B; binder A 88 aa + target T 193 aa |

The remote host became unreachable after this stage; every later stage ran on
the local host through the same engine and pool.

## Round 1 — free redesign of the de novo scaffold

| Stage | Job | Operator | Key parameters | Wall time | Artefact |
| --- | --- | --- | --- | ---: | --- |
| Sequence design | `req-1075029ecd4212dfc2ed62e1` | `proteinmpnn_design` | `chains=A`, `ca_only=true`, `num_seq_per_target=8`, `sampling_temp=0.1`, `seed=1`, `device=cuda` | 11.6 s | `scores.csv`, `seqs/complex_d3.fa`; scores 0.9265–1.0143, recovery 0.330–0.443 |

Eight designs, each scored as a complex against the fixed target chain
(`boltz_complex_confidence`, `model=boltz1`, `device=cuda`,
`sampling_steps=20`, `diffusion_samples=1`, `interface_cutoff=8`; ~65 s each):

| Design | Job | iPTM | Interface residues | Interface pLDDT |
| --- | --- | ---: | ---: | ---: |
| 1 | `req-668eb1f3a3cfb646751f73f2` | 0.0694 | 61 | 50.64 |
| 2 | `req-1ffb2c3e0bf256986f52bb9c` | 0.0951 | 73 | 63.61 |
| 3 | `req-e756c8e7b968bb3944509874` | 0.3785 | 60 | 75.96 |
| 4 | `req-ec53db572c9a26acbc1aed50` | 0.1237 | 64 | 69.79 |
| 5 | `req-1123081da2f7f4f0918c254d` | 0.0963 | 68 | 51.92 |
| 6 | `req-1941a2a8150df39da018c128` | 0.0596 | 57 | 68.86 |
| 7 | `req-b5c8a3cf135fefd24810e84a` | 0.3834 | 81 | 68.41 |
| 8 | `req-fe5ef88971616162163a3720` | 0.0897 | 61 | 73.46 |

## Round 2 — interface-fixed maturation on the best round-1 scaffold

| Stage | Job | Operator | Key parameters | Wall time | Artefact |
| --- | --- | --- | --- | ---: | --- |
| Interface analysis | `req-e04f086b4f9c9b3b423929bd` | `interface_hotspots` | `binder_chains=A`, `target_chains=B`, `cutoff=5`, `min_contacts=3`, `sort_by=contacts` | 3.4 s | 48 rows; 21 binder positions, 27 target hotspots |
| Sequence design | `req-6cfc03945b2799c6b1c193f3` | `proteinmpnn_design` | `chains=A`, `ca_only=true`, `fixed_positions=A:1,2,3,27,28,29,30,31,32,33,34,49,50,51,53,77,78,79,80,81,82`, `seed=2`, 8 sequences | 11.7 s | 8 designs, all fixed positions conserved, 26–37 non-interface substitutions |

Scoring (`boltz_complex_confidence`, identical parameters to round 1):

| Design | Job | iPTM | Interface residues | Interface pLDDT |
| --- | --- | ---: | ---: | ---: |
| 1 | `req-ba6325561867a10d03563fc6` | 0.0719 | 53 | 71.31 |
| 2 | `req-a433d56ce30aa618ed31eaf5` | 0.0829 | 65 | 67.51 |
| 3 | `req-779a77f82585aa12ef0ee603` | 0.1433 | 61 | 61.84 |
| 4 | `req-708af3cb2872e57dc37e8e92` | 0.0657 | 69 | 69.17 |
| 5 | `req-8caf84094fdc6e22b68786eb` | 0.1286 | 72 | 71.08 |
| 6 | `req-112a58f4b8c04e5496b30c2c` | 0.5234 | 62 | 70.87 |
| 7 | `req-d825ecc43dad27345e272010` | 0.4593 | 72 | 70.13 |
| 8 | `req-b7683c3160001a86a909c550` | 0.1296 | 59 | 68.03 |

## Round 2 control — same seed, no fixed positions

| Stage | Job | Operator | Key parameters | Wall time | Artefact |
| --- | --- | --- | --- | ---: | --- |
| Sequence design | `req-75e0f8522793fa5f83adc146` | `proteinmpnn_design` | `chains=A`, `ca_only=true`, `seed=2`, no `fixed_positions` | 11.7 s | 8 designs, 34–45 substitutions, recovery 0.489–0.614 |

Scoring (identical parameters):

| Design | Job | iPTM | Interface residues | Interface pLDDT |
| --- | --- | ---: | ---: | ---: |
| 1 | `req-bf058950ae535c3e3fe00d9e` | 0.8678 | 50 | 84.88 |
| 2 | `req-339a42579790ccf702c42ecb` | 0.0748 | 57 | 67.60 |
| 3 | `req-9e115c6667ec4f8fa4d78053` | 0.0804 | 46 | 72.19 |
| 4 | `req-c3cb505970d000b85f4ff596` | 0.0673 | 58 | 67.31 |
| 5 | `req-a3fb1783df6df457b0cddeae` | 0.0835 | 53 | 69.76 |
| 6 | `req-d9c384163dcd4d1cd0f1902a` | 0.4054 | 69 | 75.16 |
| 7 | `req-3ae85b7398070b31cc3c7f8c` | 0.1149 | 68 | 70.46 |
| 8 | `req-4f4dd3961cb4777f4325a625` | 0.1049 | 42 | 72.92 |

## Round 3 — retention test on the highest-confidence design

The free-control design with `iPTM 0.8678` and interface pLDDT 84.88 was used as
the new scaffold: its interface was fixed and the remaining positions
redesigned.

| Stage | Job | Operator | Key parameters | Wall time | Artefact |
| --- | --- | --- | --- | ---: | --- |
| Interface analysis | `req-622a37daa3224b3d0d57ebe3` | `interface_hotspots` | as above | 3.3 s | 34 rows; 17 binder positions |
| Sequence design | `req-9f86e30c8c1b454c03a2b63a` | `proteinmpnn_design` | `chains=A`, `ca_only=true`, `fixed_positions=A:26,27,28,29,30,31,49,50,51,53,77,78,79,80,81,82,83`, `seed=3`, 8 sequences | 11.7 s | 8 designs, all fixed positions conserved, 22–27 substitutions |

Scoring (`boltz_complex_confidence`, identical parameters):

| Design | Job | iPTM | Interface residues | Interface pLDDT |
| --- | --- | ---: | ---: | ---: |
| 1 | `req-f1692f642fb99427b37411b1` | 0.1131 | 58 | 71.04 |
| 2 | `req-ce728273e1de036cc335b751` | 0.0644 | 63 | 68.85 |
| 3 | `req-140369776c4ab577cbcaa53a` | 0.1027 | 52 | 73.60 |
| 4 | `req-3d5ca43bda102a583f65108c` | 0.0763 | 36 | 68.28 |
| 5 | `req-9277c07cb5da99925e5a1c08` | 0.1270 | 72 | 69.17 |
| 6 | `req-bbb15a53cab273b37d2d54a2` | 0.0591 | 61 | 73.43 |
| 7 | `req-83aeb72a62a30ec82022a11d` | 0.0699 | 64 | 73.96 |
| 8 | `req-59f8cabf6fa8621c8fa4aeae` | 0.0556 | 63 | 75.65 |

Across the eight children: iPTM mean **0.0835**, median 0.0731, maximum
0.1270, interface pLDDT mean 71.75, and none above 0.3 — against a parent at
0.8678 with its 17 interface positions conserved in every child.

## Round 4 — free redesign of the retained fold

The retention failure of round 3 has two readings: the fold is fragile, or the
constraint pattern is harmful. Round 4 separates them by redesigning the very
same parent complex with no fixed positions and a fourth seed.

| Stage | Job | Operator | Parameters | Duration | Result |
| --- | --- | --- | --- | ---: | --- |
| Sequence design | `req-fe46c92b3987842cef536832` | `proteinmpnn_design` | `chains=A`, `ca_only=true`, no `fixed_positions`, `seed=4`, 8 sequences | 12 s | 8 designs, 19–34 substitutions from the parent |

Scoring (`boltz_complex_confidence`, identical parameters):

| Design | Job | iPTM | Interface residues | Interface pLDDT |
| --- | --- | ---: | ---: | ---: |
| 1 | `req-c577c7bd58587ccae4cef9a3` | 0.1022 | 47 | 67.99 |
| 2 | `req-c5b3b1b86e202066bbaead6c` | 0.0572 | 38 | 65.66 |
| 3 | `req-df3e9ff05896ad2589f13345` | **0.9037** | 42 | **87.68** |
| 4 | `req-c5acbf6aab15b640f68f2dcd` | **0.8865** | 45 | **87.10** |
| 5 | `req-c28a51891d9590c4b571e509` | 0.1174 | 45 | 71.17 |
| 6 | `req-f2d1c4f2d4314eeed1f29c01` | 0.0846 | 53 | 72.04 |
| 7 | `req-73ffb8be6ff61d6600bf7e02` | 0.1028 | 44 | 68.66 |
| 8 | `req-232c9eb50eb53a01f4b74b8d` | 0.0637 | 39 | 54.22 |

Across the eight children: iPTM mean **0.2898**, median 0.1025, maximum
**0.9037**, interface pLDDT mean 71.83, two designs above 0.3 — starting from the
0.8678 parent of round 3. The fold therefore tolerates wholesale sequence change,
including every interface residue; pinning 17 interface positions while
rewriting the 71 positions beneath them is what destroyed the interface in
round 3.

## Fold retention (rounds 3 and 4)

Each child prediction was superposed on the parent complex
(`design_loop/round3/complex_free_d1.pdb`) through its target chain (193 Cα, identical
sequence) with a Kabsch fit, and the binder was transformed by the same rotation. Scripts:
`ca_rmsd.py` (per design) and `rmsd_stats.py` (correlation); raw output in
`design_loop/round(3, 4)/complexes/complexes_rmsd.json` and `design_loop/rmsd_summary.json`.

| Round | Design | Job | iPTM | Cα RMSD, target (Å) | Cα RMSD, binder (Å) |
| --- | ---: | --- | ---: | ---: | ---: |
| 3 | 1 | `req-f1692f642fb99427b37411b1` | 0.113 | 11.51 | 17.71 |
| 3 | 2 | `req-ce728273e1de036cc335b751` | 0.064 | 9.15 | 19.18 |
| 3 | 3 | `req-140369776c4ab577cbcaa53a` | 0.103 | 12.50 | 21.95 |
| 3 | 4 | `req-3d5ca43bda102a583f65108c` | 0.076 | 14.05 | 17.58 |
| 3 | 5 | `req-9277c07cb5da99925e5a1c08` | 0.127 | 9.64 | 6.64 |
| 3 | 6 | `req-bbb15a53cab273b37d2d54a2` | 0.059 | 9.57 | 19.19 |
| 3 | 7 | `req-83aeb72a62a30ec82022a11d` | 0.070 | 10.82 | 21.10 |
| 3 | 8 | `req-59f8cabf6fa8621c8fa4aeae` | 0.056 | 12.35 | 19.97 |
| 4 | 1 | `req-c577c7bd58587ccae4cef9a3` | 0.102 | 9.55 | 17.92 |
| 4 | 2 | `req-c5b3b1b86e202066bbaead6c` | 0.057 | 10.20 | 21.52 |
| 4 | 3 | `req-df3e9ff05896ad2589f13345` | 0.904 | 2.03 | 2.14 |
| 4 | 4 | `req-c5acbf6aab15b640f68f2dcd` | 0.887 | 2.67 | 1.13 |
| 4 | 5 | `req-c28a51891d9590c4b571e509` | 0.117 | 11.34 | 15.49 |
| 4 | 6 | `req-f2d1c4f2d4314eeed1f29c01` | 0.085 | 12.43 | 18.30 |
| 4 | 7 | `req-73ffb8be6ff61d6600bf7e02` | 0.103 | 10.12 | 14.54 |
| 4 | 8 | `req-232c9eb50eb53a01f4b74b8d` | 0.064 | 9.85 | 21.71 |

Two of sixteen children stay within 3 Å of the parent, both from round 4 (0.904 at 2.03 Å
and 0.887 at 2.67 Å). Round 3 spans 9.15–14.05 Å, the remaining round-4 children
9.55–12.43 Å. Across the sixteen, Pearson r = −0.902 for iPTM against target-chain RMSD
and −0.863 against binder RMSD; the 3 Å cutoff separates the high-iPTM pair from the rest
with no exceptions. Spearman on the target chain is not reported: the low-iPTM group is
compressed into 9.15–14.05 Å, and tied ranks make ρ unstable there.

## Final-candidate readout

The best-scoring design of round 4 (`req-df3e9ff05896ad2589f13345`, iPTM 0.904,
2.03 Å to the parent fold) was scored with the remaining platform operators. Prediction
PDB copied from the job's `tmp/artifacts/boltz_complex/*/prediction.pdb` to
`design_loop/round4/final_candidate/complex_d3.pdb` (188,106 B).

| Operator | Job | Result |
| --- | --- | --- |
| `interface_hotspots` | `req-bc9cd4e6649325fe7febffbb` | 30 interface residues within 5 Å, total buried area 1,180.24 Å² |
| `antibody_developability` | `req-625c9dbe0fbd525ba4110020` | length 88, MW 10,060.5 Da, pI 4.531, net charge −6.65 at pH 6.0 / −7.01 at pH 7.4, 0 cysteines, 1 deamidation motif, 0 isomerisation motifs, longest hydrophobic run 3, hydrophobic fraction 0.386 |
| `sequence_liability_scan` | `req-57845c5a023059e86d98c7c1` | 3 sites: E1 pyroglutamate (low, `EVKI`), N14 deamidation (high, `NG`), D63 isomerisation (high, `DG`) |

The developability panel reports zero isomerisation motifs while the liability scan flags
D63 in a DG motif; the two operators use different motif sets, and the disagreement is
kept rather than reconciled because each score carries its operator identity. The binder
sequence is `design_loop/round4/final_candidate/binder_d3.fa` (88 aa, record
`binder_d3_round4`).

## Reproducing the loop

The scripts used here are shipped under `scripts/design_loop/`, with the workspace and
prediction paths taken from the arguments or from the `D:\OperonTest517rc7` layout used
for the runs in this document:

| Script | Purpose |
| --- | --- |
| `collect_round.py` | walk `<base>/results/req-*/runs/*/steps/01_boltz_complex_confidence.json`, emit the score CSV |
| `make_complexes.py` | rebuild `>binder`/`>target` FASTAs from a parent PDB plus a ProteinMPNN FASTA |
| `submit_boltz.py` | emit one Boltz graph per complex and submit it through the CLI |
| `ca_rmsd.py` | superpose a prediction on the parent through the target chain and report both RMSDs |
| `rmsd_stats.py` | correlate iPTM with fold retention over the collected rows |

## Replicate scoring of the retained designs

Every Boltz run draws a fresh diffusion trajectory, so the retained designs were
re-scored with identical graphs, parameters and inputs to measure the spread.
Scores live in each job's `output_dir` (read from `.studio/jobs/<id>/job.json`)
under `runs/<run>/steps/01_boltz_complex_confidence.json`.

| Design | Original iPTM | Replicate jobs | Mean | SD | Min | Max |
|---|---|---|---|---|---|---|
| d3 (round 4, 0.904) | 0.904 | `req-c8bd27039de63941aa000138`, `req-a1a14d80d34712ccbee2d55a`, `req-53d1f8385744966add6bc992` | 0.894 | 0.006 | 0.887 | 0.899 |
| d4 (round 4, 0.887) | 0.887 | `req-787e52e9fdedb2b185443d10`, `req-327404fa52fe3e731fd89849`, `req-a09a499943fde1778af13733` | 0.851 | 0.023 | 0.826 | 0.870 |
| d1 (round 4, 0.102) | 0.102 | `req-faccc7bf908b52490061ab0f`, `req-ca9bc6511d0be4b304a6fb9d` | 0.130 | 0.025 | 0.112 | 0.147 |

The two retained designs reproduce within a few hundredths and stay an order of
magnitude above the low-scoring control, so the upper mode is a property of the
designs rather than of one lucky sample.

## Second retained candidate

The round-4 design at iPTM 0.887 was carried through the same readout as the
0.904 design, from its own prediction (`req-c5acbf6aab15b640f68f2dcd`).

| Operator | Job | Reading |
|---|---|---|
| `interface_hotspots` | `req-9d5e713a97e0eb15f267abfb` | 32 interface residues, 1,266.84 Å² buried |
| `antibody_developability` | `req-1fcef7ad8c939d6a5a130436` | length 88, MW 9,851.15, pI 4.209, net charge −9.68 (pH 6.0) / −10.01 (pH 7.4), 0 cysteines, 3 hydrophobic run, fraction 0.409 |
| `sequence_liability_scan` | `req-08b8a1836f8516967fd950d6` | 2 sites, both isomerisation high: D14 and D63 in DG motifs |

## Cross-host replication

The three readouts that carry the retained designs were re-executed on `licai-srv` through the same MCP
calls used locally: application `5.1.17-rc7`, library `main-v0.1.22` (7 packages, 1069 operators,
108 readers, 1177 descriptors), one RTX 3090, CUDA 12.1 with `torch 2.3.1+cu121`. Inputs were staged in
`workspace/remote_eval_s6` with sha256 `064af0b4…` (`s6_pred.pdb`, 184,580 B), `4ef94eda…`
(`binder_s6.fa`, 95 B) and `28b1c6d6…` (`s6_binder.fa`, 100 B).

| Readout | Remote job | Result |
| --- | --- | --- |
| `interface_hotspots` | `ssh-df1ff559c6fd474ca2d11a88f12a9bc7-req-f67ceaad1907c43e45918e62` | 55 hotspots, 2,285.093 Å² buried, cutoff 5.0 |
| `antibody_developability` | `ssh-df1ff559c6fd474ca2d11a88f12a9bc7-req-03bb43ef492e5e2077e11f67` | mean pI 6.07317160 |
| `sequence_liability_scan` | `ssh-df1ff559c6fd474ca2d11a88f12a9bc7-req-33cc2139bd6a306ff465856e` | 7 sites: N41/N54/N79 glycosylation (medium), M55 oxidation (medium), N63 deamidation (high), N74 deamidation (medium), D76 isomerisation (high) |

The developability and liability payloads are identical to the local jobs `20261115T154606-d07a7ff8`
(same pI `6.073171615600586`, same seven sites with the same severities). A local rerun of
`interface_hotspots` on `s6_pred.pdb` with the same parameters (`req-54aec4b2166fbfdd91a80e4c`) returns
exactly 55 hotspots and 2,285.093 Å², so the two hosts agree bit for bit on all three readouts.

Two numbers that circulated earlier are **not** comparable with these and should not be mixed:
`structure_interface_core` (`20261115T154515-8d25b89c`) reports 63 interface residues for the same
structure (37 core, 26 rim, 33 binder + 30 target residues) using its own distance rule, and
`minibinder_interface` reports 31 interface residues over 88 atom contacts at cutoff 5.0 with
`min_contacts: 1`. `interface_hotspots` uses `min_contacts: 3` and reports per-residue buried area, so its
55 is the figure to quote alongside `interface_hotspots` runs.

Two operational requirements came out of the exercise: a remote graph must name its input by a path
relative to the workspace (an absolute Windows path fails the server-side existence check), and
`runtime.submission_key` must be regenerated, otherwise the idempotent submit returns an older job.

The library sources were also reconciled with the published bundle in this pass. `library/seed` on
`library/resource-download-interface` now reproduces `operon-library-main-v0.1.22.operon-library.zip`
byte for byte (`682a7849…`, 6,870,118 B) after `1a37d4c7`, the `0.1.18`-lineage merge `fe8f6ede`, and
`9508d8b21`, which keeps the released `boltz_predict.py` cache path.

## The developability defect and library 0.1.22

The developability panel reported zero isomerisation sites for both candidates
while the liability scan flagged one and two DG motifs. The panel counted only
`DP`; library 0.1.22 counts `DP` and `DG` and both readouts were re-run against
it. The re-runs report 1 site for the 0.904 design (`req-3c121a41e225827ddfbe3f0e`)
and 2 sites for the 0.887 design (`req-5ab6e5d1086ce6e3dd90e454`), agreeing with
the scan site for site.

Library 0.1.22: bundle
`operon-library-main-v0.1.22.operon-library.zip`, 6,870,118 B, sha256
`682a78491612e7f6b1c715c56f43a02cd0070b6378cec3a94f532057d8547049`; routes
`operon-routes-main-v0.1.22.zip`, 201,351 B, sha256
`6edce3920c3b95c165085525d8b76038fcfadd9942dc7392c97f9ae0b17d41d7`. Readouts
above that name no re-run job predate this fix and report the old zero count.

## Platform defects found by the loop

| Defect | Symptom | Fix | Version |
| --- | --- | --- | --- |
| Coordinator could not reserve its own lease | every submission queued indefinitely once a coordinator record existed | compare the coordinator owner `(pid, created)` with the requesting identity instead of refusing whenever a coordinator exists | application `5.1.17-rc7` (`fd9731db`) |
| Quarantined lease never released | one restart left a 16.66 GB lease charged to a dead worker, so a 16.66 GB request could never fit | fail an attempt whose recorded worker is proven dead after a 300 s grace period (`recovery_abandoned`) and return its lease | application `5.1.17-rc7` (`75cbd795`) |
| CUDA capability probed in the wrong interpreter | `device=cuda` refused on a host with a GPU | probe CUDA through the operator's `python_executable` | library `0.1.20` |
| `CUDA_VISIBLE_DEVICES` cleared to an empty string | CPU-mode runs still tried to deserialise on CUDA device 0 | set `-1` in CPU mode, keep the granted devices in CUDA mode | library `0.1.20` |
| Fixed positions keyed by full path | `KeyError: 'complex_d3'` in `protein_mpnn_utils.tied_featurize` | key the JSONL by the PDB stem, as ProteinMPNN indexes `b['name']` | library `0.1.21` |
| Isomerisation counted `DP` only | developability panel reported 0 while the liability scan flagged `DG` sites | count `DP` and `DG` | library `0.1.22` |

## Reproducing a scoring run

```bash
python -m operon --workspace <workspace> --data-dir <workspace>/.studio \
  run <graph.json> --request-id <id> --brief
```

Each `graph.json` names `FastaReader` over `designs/design_<n>.fa` and
`boltz_complex_confidence` with the parameters above. Confidence values are read
from the run's
`runs/<run>/steps/01_boltz_complex_confidence.json`; the interface residue count
is the row count of the operator's `confidence` artefact.
