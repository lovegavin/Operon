# Competitor capability gap matrix v3 (post 6.0.1)

Scope: capabilities absent from the 1017-operator catalog that have a deterministic implementation, public or synthetic data, and at least two independent oracles. Dependency versions are those verified in the WSL environment: numpy 2.1.3, scipy 1.17.1, scikit-learn 1.6.1, statsmodels 0.15.0, lifelines 0.30.3, torch 2.11.0, transformers 4.57.6, esm 3.4.2, biotite 1.8.0, openmm 8.6.1, propka 3.5.1, pdb2pqr 3.8.0, umap 0.5.12, jax 0.11.2, pytorch-lightning 2.5.0, rdkit 2026.09.1, scanpy 1.12.5, igraph 1.0.0, leidenalg 0.12.0, dendropy 5.1.3, mdtraj 1.11.2, biopython 1.88.

| Capability | Competitor | Status | Plan |
| --- | --- | --- | --- |
| Split conformal regression intervals | MAPIE 0.9, crepes 0.9 | implemented b82 (conformal_split_regression) | two independent quantile implementations |
| Conformal classification sets | MAPIE 0.9 | implemented b82 (conformal_classification_sets) | manual score threshold + coverage oracle |
| Exact change-point segmentation | ruptures 1.1.9, changepoint 2.2.4 | implemented b82 (changepoint_pelt) | brute-force dynamic program oracle |
| Discrete HMM Viterbi decoding | hmmlearn 0.3.3, pomegranate 1.1 | implemented b82 (hidden_markov_viterbi) | exhaustive path enumeration for short sequences |
| Local-level Kalman filter | statsmodels 0.15.0, filterpy 1.4.5 | implemented b82 (kalman_local_level) | independent recursion + statsmodels comparison |
| Discrete HMM training (Baum-Welch) | hmmlearn 0.3.3, pomegranate 1.1 | implemented b86 (hmm_baum_welch) | forward-backward likelihood identity and convergence diagnostics |
| Rauch-Tung-Striebel smoothing | statsmodels 0.15.0, filterpy 1.4.5 | implemented b86 (kalman_smoother) | independent matrix-form RTS recursion |
| Bootstrap particle filter | filterpy 1.4.5, pymc 5.x | implemented b86 (particle_filter_bootstrap) | analytic Kalman posterior for the linear-Gaussian case |
| Causal forests / uplift | econml 0.15, causalml 0.15 | implemented b83 (uplift_t_learner, uplift_qini_curve) | linear T-learner and normalised cumulative-uplift oracle; causal forest still blocked |
| CRISPR off-target specificity | CRISPOR 5.0, FlashFry 2.0 | implemented b83 (crispr_mit_specificity) | Hsu MIT weights and hand score; CFD matrix remains blocked by licence |
| Flux balance analysis | cobra 0.29, COBRApy | implemented b83 (fba_flux_balance) | vertex enumeration plus hand-solved network |
| Image segmentation / nuclei counting | scikit-image 0.25, CellProfiler 4.2 | implemented b84 (image_otsu_threshold, image_connected_components, image_histogram_equalization, image_sobel_gradient) | synthetic images with known object counts |
| Tabular neural networks / autoencoder anomaly | PyTorch 2.11, scikit-learn 1.6 MLP | implemented b85 (mlp_classifier, mlp_regressor, autoencoder_anomaly) | independent IRLS, OLS and SVD oracles with three-decimal cross-platform rounding |
| Mutational signatures / VAE anomaly / DeepSurv | SigProfiler 1.x, PyTorch 2.11, lifelines 0.30 | implemented b87 (mutational_signature_decomposition, vae_anomaly, deep_survival) | independent support-enumeration NNLS, closed-form VAE score, lifelines CoxPH; three-decimal cross-platform rounding |
| Attention/CNN classifiers and Shapley attribution | PyTorch 2.11, scikit-learn 1.6, SHAP 0.4x | implemented b88 (transformer_classifier, cnn_image_classifier, kernel_shap) | sklearn MLP parity and closed-form ridge Shapley identity; three-decimal cross-platform rounding |
| Graph neural networks (node classification) and generative density models | PyTorch Geometric 2.6, scvi-tools 1.2 | implemented b89 (gcn_node_classifier, normalizing_flow_density) | sklearn logistic parity on features, two-layer RealNVP with KDE density check |
| Ion mobility collision cross-section | PNNL CCS 4.0 | planned b84 | formula oracle and independent implementation |
| Protein language model embeddings | ESM3 3.4.2 | covered (esm3_embedding, esm_embedding) | existing operators |
| Structure generation | RFdiffusion, LigandMPNN | covered | existing operators |
| Nucleotide language model | Nucleotide Transformer 2.0 | blocked | 2.5 GB weights and no second oracle |
| Single-cell foundation model | scGPT, Geneformer | blocked | checkpoint download and no deterministic oracle |
| Molecular diffusion generation | DiffSBDD, torsional diffusion | blocked | GPU weights and no reproducible oracle |
| Clinical variant interpretation | ClinVar, ACMG | blocked | licence-restricted data and no deterministic oracle |


### b90 implemented (2026-11-08)

| capability | competitors | operator | verification |
| --- | --- | --- | --- |
| Gradient-boosted classification | LightGBM 4.7, XGBoost 3.4, scikit-learn 1.6 | `lightgbm_classifier` | synthetic+hand 10/10, WSL=Windows |
| Gradient-boosted regression | XGBoost 3.4, LightGBM 4.7, CatBoost | `xgboost_regressor` | synthetic+hand 10/10, WSL=Windows |
| Density-based clustering with noise | HDBSCAN 0.8, scikit-learn 1.6 | `hdbscan_cluster` | synthetic+hand 10/10, WSL=Windows |
