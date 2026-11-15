# Design-loop scripts

These are the scripts that produced the rounds recorded in
`docs/releases/design-loop.md`. They are kept as run — the workspace, install root and
interpreter used for the reported numbers appear as constants at the top of each file
(`D:\OperonTest517rc7`, application `5.1.17-rc7`, library `main-v0.1.21`). Point them at
another installation by editing those constants; nothing else in the flow depends on the
original machine.

| Script | Purpose |
| --- | --- |
| `collect_round.py <base> <csv>` | walk `<base>/results/req-*/runs/*/steps/01_boltz_complex_confidence.json`, emit iPTM / interface count / interface pLDDT and an 8 Å CA contact count |
| `make_complexes.py` | rebuild `>binder` / `>target` FASTAs from a parent complex PDB plus a ProteinMPNN FASTA |
| `submit_boltz.py` | write one Boltz graph per complex and submit each through `operon run` |
| `ca_rmsd.py <base>` | superpose each prediction on the parent through the target chain (Kabsch) and report target- and binder-chain CA RMSD |
| `rmsd_stats.py` | correlate iPTM with the target-chain RMSD over the collected rows |

The CA RMSD scripts need NumPy; they were run with the `boltz` isolated environment's
interpreter (`library/environments/boltz/python.exe`, NumPy 1.26.4). The others need only
the application runtime.
