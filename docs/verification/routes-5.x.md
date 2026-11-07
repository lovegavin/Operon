

## b65b CNV score, NNLS deconvolution and MHC anchors

- Commit: this batch; branch `release/5.0`.
- Inputs (sha256): expr `8d7423753b1a4a0be939c55722b114c08033311a252282268af2b05927875204`, arms `212a08d3dee7b47b39971c8e57aa864a07f790aab8081319c7a1ede71c1c523a`, bulk `090f3d14404341fd4bf97a1692bcb02f0a413f0fbb73cb5141de2ad52434021f`, sig `ecde37e25eae083372f80f78b1d744629167113b45f3ac0a84c6ee2347a42478`, peptides `3b89e8a5a0c61676f35527cd3a45a32f21a1fb1d09924e4f9a7bffc21fcb2284`. Synthetic (`mode=synthetic`).
- Route `workdir/b65b_route`: three CsvReader sources pair into `sc_cnv_score`, `sc_deconvolution`, `mhc_binding_motif`, each followed by `export_results`; 6/6 steps.
- Values: CNV cell0 0.971404521, cell1 0.908248290, cell2 0.945435403, cell3 0.908248290 (2 arms); deconvolution sample0 0.839347881/0.160652119, sample1 0.332447751/0.667552249, sample2 0.477299869/0.522700131; MHC ALMFGILMV 5, AAAAAAAAA 1, SLFNVYLLT 3, PEPTIDE 0.
- Oracles: `C:/Users/Public/b65b_oracle.py` recomputes arm-level absolute z-scores, a Lawson-Hanson NNLS, and the anchor score from definitions; all rows agree (deconvolution max delta 1.1e-16). `tests/test_b65b.py`: 3 passed.
- Three-end: WSL and Windows (`D:\Operon`, py 3.12, registry 995) identical md5: cnv `d26dbe008b30ca86c2772c7d0af9a141`, deconv `5e083019d8d7ab636468f54e0e4431c8`, mhc `4c4f935d0cbf45b06a306e28292a9a04`. srv SKIP: `ssh srv` unresolvable.
- Limits: CNV score needs an arm map and uses a z-score, not a segment/allele model; deconvolution uses unregularised NNLS; MHC anchors use a binary hydrophobicity rule, not a trained binding predictor.


## b72c — tree consensus, quartet support and root-to-tip dating

Operators: `tree_consensus`, `tree_quartet_support`, `tree_dating` (Phylogenetics,
protocol 3.7). Inputs are synthetic Newick strings, quartet expectations and tip dates.

Route: `workdir/b72c_route` (6 steps, CHECK OK, 6/6 complete).

Input SHA-256:
- trees.csv `bcb23d4e7496bbee0fc8575e5b339f68b1a70f5260186026b4fbd1b9d7e9cafa`
- quartets.csv `3beb09de5c20c2528c3a506d7285b59c4d8f678c9270580e9c675575ab7590c2`
- dates.csv `4393456f59c11f348f7865b5b24f605eef3dd5007d6da0542d45698771090c7b`

Exported values (CSV, LF):
- cons.csv: A|B support 1.0/count 2/size 2; C|D 1.0/2/2.
- quart.csv: A,B,C,D match 1/topo 0/expected 0; A,C,B,D 0/0/1; A,D,B,C 0/0/2; overall 0.333333333.
- dating.csv: slope 1.0, intercept 2.0, r2 1.0, n_tips 4.

Oracles: independent stdlib Newick parser and hand OLS in `C:/Users/Public/b72c_oracle.py`,
3/3 pass (`workdir/b72c_oracle.json`); consensus clades, four-point topology and
root-to-tip slope/intercept/r2 all exact to 1e-9.

Three-end:
- WSL: 6/6, md5 cons `3902d4739736db3b31a793b7cfd3743f`, quart `b1754f7a77ba17639dd88480fe9f761a`, dating `ad84acd3048575fdde97494163ece69c`.
- Windows (D:\Operon, py3.12, registry 998): 6/6, same three md5 MATCH.
- srv: SKIP, no ssh profile configured.

Limitations: quartet/dating use the first tree row only; no branch supports; synthetic
dataset; newline-normalised CSV.
