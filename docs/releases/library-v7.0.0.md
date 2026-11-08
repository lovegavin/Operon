# Operon Operator Library v7.0.0

**Release date:** 2026-11-08

Feature release for Operon Studio 3.1.2. The library grows from 1017 to 1063
operators while keeping wire protocol 3, SDK 3.7 declarations and the 78
existing route templates.

## What changed

- 46 new operators in fourteen areas: conformal prediction, change-point
  detection, hidden Markov models and Kalman/particle filters, causal forests,
  uplift modelling, flux-balance analysis, CRISPR CFD/MIT off-target scoring,
  classical and learned image operators, torch MLP/autoencoder/CNN/Transformer
  classifiers, survival and generative models (DeepSurv, VAE, RealNVP),
  anomaly detection (isolation forest, LOF, HDBSCAN), gradient boosting
  (LightGBM, XGBoost), DNA language-model embeddings (Nucleotide Transformer
  v2 50M), regression discontinuity, propensity-score matching, Bayesian
  linear regression, graph pseudotime and Gaussian blur. The pre-existing
  `iv_2sls` operator (1.4.0 API) keeps its original contract and is exercised by
  the b94 route.
- Dependency versions are pinned in operator metadata: `numpy>=1.24`,
  `scipy>=1.11`, `scikit-learn>=1.5`, `statsmodels>=0.14`, `torch>=2.4`,
  `transformers>=4.45`, `lightgbm>=4.5`, `xgboost>=2.1`, `hdbscan>=0.8`,
  `econml>=0.15`, `lifelines>=0.29` (tested: numpy 2.1.3, scipy 1.17.1,
  scikit-learn 1.6.1, statsmodels 0.15.0, torch 2.11.0+cu130,
  transformers 4.57.6, lightgbm 4.7.0, xgboost 3.4.1, hdbscan 0.8.44,
  econml 0.17.0, lifelines 0.30.3).
- Nucleotide Transformer v2 50M weights are optional: the DNA embedding and
  variant-effect operators require `resources.external_models` and skip with
  an explicit message when the local cache is absent. Every route in this
  release runs without large weights.

## Compatibility

| Item | Value |
| --- | --- |
| Operon Studio | 3.1.2 |
| Operon SDK | 3.7.0 |
| Operator protocol | integer 3, `protocol_revision` 3.7 |
| `minimum_application` / `build_application` | 3.1.2 / 3.1.2 |

## Verification

- Registry: 1063 operators, 108 Readers, 7 packages, 78 routes, 0 errors.
- Full pytest on the NumPy 2.1.3 environment: recorded in
  `docs/verification/routes-5.x.md` and the release checklist.
- Route evidence for the new batches (b82-b95) is in
  `docs/verification/routes-5.x.md`, with synthetic fixtures, two independent
  oracles per domain and WSL/Windows byte-identical exports where the
  dependency set is portable. Batches that need numba-only or GPU-only
  dependencies record an explicit SKIP and reason.
- Capability gaps are tracked in
  `docs/verification/competitor-gap-matrix-v3.md`.

## Assets

The tag `library-v7.0.0` produces Linux and Windows `.operon-library.zip`
bundles, `Operon-Routes-v7.0.0.zip`, `Operon-Quickstart-v7.0.0.zip`, the
`operon_builtin_library-7.0.0` wheel, bilingual quick starts, the three
dependency installers, `SHA256SUMS.txt` and the two verification JSON files.
