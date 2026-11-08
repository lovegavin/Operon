# Bisulfite conversion rate

## Purpose

Estimate bisulfite conversion efficiency from converted and unconverted cytosine counts with a Wilson interval.

## Inputs

One table with numeric columns `converted` and `unconverted`.

## Outputs

A two-dimensional form with a single `row` entry and the statistic columns
`n_sites`, `converted`, `unconverted`, `conversion_rate`, `ci_low`, `ci_high`..

## Parameters

- `output`: output name (default `conversion`).
- `row_dim`, `field_dim`: input dimension names (defaults `row`, `field`).

## Limitations

The estimate assumes every cytosine has the same conversion probability; non-CpG context weighting is not modelled.
