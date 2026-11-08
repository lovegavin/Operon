# Allele-specific methylation

## Purpose

Test allele-specific methylation from methylated and unmethylated read counts per allele using Fisher's exact test with BH correction.

## Inputs

One table with columns `a_methylated`, `a_unmethylated`, `b_methylated`, `b_unmethylated`.

## Outputs

A two-dimensional form with a single `row` entry and the statistic columns
`n_sites`, `n_tested`, `n_significant`, `mean_abs_diff`, `min_p`..

## Parameters

- `output`: output name (default `asm`).
- `row_dim`, `field_dim`: input dimension names (defaults `row`, `field`).

## Limitations

Sites with zero coverage on either allele are counted but not tested; no phasing or read-level linkage is used.
