# Rauch-Tung-Striebel Kalman smoother

Run the Rauch-Tung-Striebel smoother for a local-level model and report filtered and smoothed state estimates with their variances.

## Purpose

Batch b86 state-space operator. Dependencies: numpy>=1.24 (tested 2.1.3).

## Parameters

- `process_var`: state innovation variance (default 1.0)
- `obs_var`: observation variance (default 1.0)

## Limitations

Discrete local-level model only; no missing observations.
