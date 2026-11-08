# Bootstrap particle filter

Bootstrap particle filter for a local-level model with seeded resampling; reports the filtered mean, variance, effective sample size and log-likelihood.

## Purpose

Batch b86 state-space operator. Dependencies: numpy>=1.24 (tested 2.1.3).

## Parameters

- `n_particles`: number of particles (default 200)
- `process_var`: state innovation variance (default 1.0)
- `obs_var`: observation variance (default 1.0)
- `seed`: random seed (default 0)

## Limitations

Discrete local-level model only; no missing observations.
