# Competitor capability gap matrix v3 (post 6.0.1)

Scope: capabilities absent from the 1017-operator catalog that have a deterministic implementation, public or synthetic data, and at least two independent oracles. Dependency versions are those verified in the WSL environment: numpy 2.1.3, scipy 1.17.1, scikit-learn 1.6.1, statsmodels 0.15.0, lifelines 0.30.3, torch 2.11.0, transformers 4.57.6, esm 3.4.2, biotite 1.8.0, openmm 8.6.1, propka 3.5.1, pdb2pqr 3.8.0, umap 0.5.12, jax 0.11.2, pytorch-lightning 2.5.0, rdkit 2026.09.1, scanpy 1.12.5, igraph 1.0.0, leidenalg 0.12.0, dendropy 5.1.3, mdtraj 1.11.2, biopython 1.88.

| Capability | Competitor | Status | Plan |
| --- | --- | --- | --- |
| Split conformal regression intervals | MAPIE 0.9, crepes 0.9 | implemented b82 (conformal_split_regression) | two independent quantile implementations |
| Conformal classification sets | MAPIE 0.9 | implemented b82 (conformal_classification_sets) | manual score threshold + coverage oracle |
| Exact change-point segmentation | ruptures 1.1.9, changepoint 2.2.4 | implemented b82 (changepoint_pelt) | brute-force dynamic program oracle |
| Discrete HMM Viterbi decoding | hmmlearn 0.3.3, pomegranate 1.1 | implemented b82 (hidden_markov_viterbi) | exhaustive path enumeration for short sequences |
| Local-level Kalman filter | statsmodels 0.15.0, filterpy 1.4.5 | implemented b82 (kalman_local_level) | independent recursion + statsmodels comparison |
| Causal forests / uplift | econml 0.15, causalml 0.15 | planned b83 | no installed package; implement T-learner and doubly robust estimator directly |
| CRISPR off-target CFD score | CRISPOR 5.0, FlashFry 2.0 | planned b83 | public CFD matrix, two independent scorers |
| Flux balance analysis | cobra 0.29, COBRApy | planned b83 | scipy.optimize.linprog oracle plus hand-solved network |
| Image segmentation / nuclei counting | scikit-image 0.25, CellProfiler 4.2 | planned b84 | synthetic images with known object counts |
| Ion mobility collision cross-section | PNNL CCS 4.0 | planned b84 | formula oracle and independent implementation |
| Protein language model embeddings | ESM3 3.4.2 | covered (esm3_embedding, esm_embedding) | existing operators |
| Structure generation | RFdiffusion, LigandMPNN | covered | existing operators |
| Nucleotide language model | Nucleotide Transformer 2.0 | blocked | 2.5 GB weights and no second oracle |
| Single-cell foundation model | scGPT, Geneformer | blocked | checkpoint download and no deterministic oracle |
| Molecular diffusion generation | DiffSBDD, torsional diffusion | blocked | GPU weights and no reproducible oracle |
| Clinical variant interpretation | ClinVar, ACMG | blocked | licence-restricted data and no deterministic oracle |
