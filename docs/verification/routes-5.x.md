

## b65b CNV score, NNLS deconvolution and MHC anchors

- Commit: this batch; branch `release/5.0`.
- Inputs (sha256): expr `8d7423753b1a4a0be939c55722b114c08033311a252282268af2b05927875204`, arms `212a08d3dee7b47b39971c8e57aa864a07f790aab8081319c7a1ede71c1c523a`, bulk `090f3d14404341fd4bf97a1692bcb02f0a413f0fbb73cb5141de2ad52434021f`, sig `ecde37e25eae083372f80f78b1d744629167113b45f3ac0a84c6ee2347a42478`, peptides `3b89e8a5a0c61676f35527cd3a45a32f21a1fb1d09924e4f9a7bffc21fcb2284`. Synthetic (`mode=synthetic`).
- Route `workdir/b65b_route`: three CsvReader sources pair into `sc_cnv_score`, `sc_deconvolution`, `mhc_binding_motif`, each followed by `export_results`; 6/6 steps.
- Values: CNV cell0 0.971404521, cell1 0.908248290, cell2 0.945435403, cell3 0.908248290 (2 arms); deconvolution sample0 0.839347881/0.160652119, sample1 0.332447751/0.667552249, sample2 0.477299869/0.522700131; MHC ALMFGILMV 5, AAAAAAAAA 1, SLFNVYLLT 3, PEPTIDE 0.
- Oracles: `C:/Users/Public/b65b_oracle.py` recomputes arm-level absolute z-scores, a Lawson-Hanson NNLS, and the anchor score from definitions; all rows agree (deconvolution max delta 1.1e-16). `tests/test_b65b.py`: 3 passed.
- Three-end: WSL and Windows (`D:\Operon`, py 3.12, registry 995) identical md5: cnv `d26dbe008b30ca86c2772c7d0af9a141`, deconv `5e083019d8d7ab636468f54e0e4431c8`, mhc `4c4f935d0cbf45b06a306e28292a9a04`. srv SKIP: `ssh srv` unresolvable.
- Limits: CNV score needs an arm map and uses a z-score, not a segment/allele model; deconvolution uses unregularised NNLS; MHC anchors use a binary hydrophobicity rule, not a trained binding predictor.
