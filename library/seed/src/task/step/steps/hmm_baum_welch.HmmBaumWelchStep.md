# Baum-Welch HMM training

Fit a discrete hidden Markov model with scaled Baum-Welch EM and report the final log-likelihood, iteration count and transition/emission matrices.

## Purpose

Batch b86 state-space operator. Dependencies: numpy>=1.24 (tested 2.1.3).

## Parameters

- `n_states`: number of hidden states (default 2)
- `n_iter`: maximum EM iterations (default 100)
- `tol`: log-likelihood convergence tolerance (default 1e-06)
- `seed`: random seed for the deterministic initialisation (default 0)

## Limitations

Discrete local-level model only; no missing observations.
