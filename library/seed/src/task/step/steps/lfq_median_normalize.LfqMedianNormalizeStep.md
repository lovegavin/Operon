# Median-normalize an LFQ matrix

## Purpose

Median normalization removes sample loading differences by scaling
each sample so that its median peptide intensity matches a common target.

The operator accepts a 2D protein x sample matrix. Non-finite and
non-positive entries are treated as missing and stay missing after scaling.
Per-sample medians and scaling factors are reported in `info`.

Limitations: median normalization assumes most proteins are unchanged and
does not impute missing values; it is not a replacement for intensity-based
absolute quantification.

## Source

`lfq_median_normalize.py`
