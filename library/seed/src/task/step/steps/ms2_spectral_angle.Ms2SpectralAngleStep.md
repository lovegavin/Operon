# MS2 spectral angle

## Purpose

Computes the spectral angle between two centroid spectra after square-root intensity scaling.

## Inputs

Two peak tables with `mz` and `intensity` columns.

## Parameters

- `mz_tolerance`: maximum absolute m/z difference for a match.

## Limitations

Greedy one-to-one matching; no intensity normalization beyond square root; no precursor filtering.
