

## b65 spatial transcriptomics: kNN graph, domains, Moran's I

- Commit: this batch; branch `release/5.0`.
- Inputs (sha256): coords `50bb60b7697e795628b67c95243f12e9da72d62f5e88c3ee8ed8ac9467db4939`, counts `f181d69431352bb55418532a8ba22f72358e9220441f57c936e553b27f135619`. Synthetic 8-cell grid (`mode=synthetic`).
- Route `workdir/b65_route`: CsvReader -> `sc_spatial_neighbors` (k=3), `sc_spatial_domains` (k=3, 2 domains), `sc_spatial_variable_genes` (Moran's I, k=3) -> three `export_results`; 6/6 steps complete.
- Values: kNN sigma 2.795445511; c1-c2 weight 0.923135395, c1-c3 0.93562284; domains c1-c5 domain 0 (purity 1.0), c6-c8 domain 1 (purity 0.333/0.333/0.667); Moran g1 0.203417751 (z 0.647821007, p 0.517100727), g2 -0.019121703, g3 0, g4 -0.315356655.
- Oracle: `C:/Users/Public/b65_oracle.py` recomputes the kNN weights (independent distance loops, median sigma), Moran's I and the k-means centroid fixed point; 3/3 pass, max deltas 4.9e-10 (weights) and 2.4e-10 (Moran), domain fixed point exact (`workdir/b65_route/oracle_b65.json`).
- Tests: `tests/test_b65_panel.py`, 3 passed.
- Three-end: WSL and Windows (`D:\Operon`, py 3.12, registry 992) identical md5: neighbors `93fe6af61c365a5002ed8e37d0d66ec6`, domains `a36e8151c0e8aba7a9d4f6e1bde583aa`, svg `5f0e60dd959c499ba4b475c574b03f93`. srv SKIP: `ssh srv` is not resolvable.
- Limits: sigma is the global median kNN distance; k-means uses farthest-first deterministic initialisation, not SpaGCN/Leiden; Moran's I uses a symmetric Gaussian weight matrix and a normal-approximation p-value.
