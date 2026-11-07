# Spectrum library match

## Purpose

Cosine score of each query spectrum against a library of spectra.

## Inputs

- Input 1: Form with row axis `peak` and field axis `field`.
- Input 2: Form with row axis `peak` and field axis `field`.

## Output

A 2-D numeric Form: rows are entries, columns are the reported statistics.

## Limitations

Synthetic test data only; no retention time, charge state or noise model is
inferred. The implementation reports the stated algebra, not a biological
identification.
