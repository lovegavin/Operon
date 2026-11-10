# Quantile-normalize an LFQ matrix

## Purpose

Quantile normalization forces all sample columns to share one
empirical intensity distribution, removing both loading and compression
differences between runs.

Input is a 2D protein x sample matrix; non-finite values are left untouched.
The reference distribution is the per-rank mean over samples.

Limitations: quantile normalization assumes the same underlying distribution
in every sample and can remove real global abundance changes; do not use it
when a large fraction of proteins is expected to change.

## Source

`lfq_quantile_normalize.py`
