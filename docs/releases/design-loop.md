# Design-loop provenance index

This file lists every job that produced the design-loop results reported in the
manuscript, with the parameters that matter for reproduction and the identifiers
needed to retrieve the artefacts. All jobs were submitted through the Operon
Model Context Protocol surface (`operon_submit`) or, for the batched scoring
runs, through the equivalent `operon run` command over the same service; none
was executed by a shell pipeline.

Environment: application `5.1.17-rc7` (`D:\OperonTest517rc7`, version directory
`5.1.17-f397f8157e17`), operator library `main-v0.1.21` (1069 operators,
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

## Platform defects found by the loop

| Defect | Symptom | Fix | Version |
| --- | --- | --- | --- |
| Coordinator could not reserve its own lease | every submission queued indefinitely once a coordinator record existed | compare the coordinator owner `(pid, created)` with the requesting identity instead of refusing whenever a coordinator exists | application `5.1.17-rc7` (`fd9731db`) |
| Quarantined lease never released | one restart left a 16.66 GB lease charged to a dead worker, so a 16.66 GB request could never fit | fail an attempt whose recorded worker is proven dead after a 300 s grace period (`recovery_abandoned`) and return its lease | application `5.1.17-rc7` (`75cbd795`) |
| CUDA capability probed in the wrong interpreter | `device=cuda` refused on a host with a GPU | probe CUDA through the operator's `python_executable` | library `0.1.20` |
| `CUDA_VISIBLE_DEVICES` cleared to an empty string | CPU-mode runs still tried to deserialise on CUDA device 0 | set `-1` in CPU mode, keep the granted devices in CUDA mode | library `0.1.20` |
| Fixed positions keyed by full path | `KeyError: 'complex_d3'` in `protein_mpnn_utils.tied_featurize` | key the JSONL by the PDB stem, as ProteinMPNN indexes `b['name']` | library `0.1.21` |

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
