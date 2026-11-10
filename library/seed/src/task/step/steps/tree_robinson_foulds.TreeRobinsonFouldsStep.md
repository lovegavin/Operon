# Robinson-Foulds distance

## Purpose

Compute the Robinson-Foulds distance between two Newick trees with identical taxon sets.

## Inputs

Two tables whose `newick` column holds one Newick tree each.

## Outputs

A two-dimensional form with a single `row` entry and the statistic columns
`rf`, `max_rf`, `normalized_rf`, `n_taxa`, `n_splits_a`, `n_splits_b`..

## Parameters

- `output`: output name (default `rf`).
- `row_dim`, `field_dim`: input dimension names (defaults `row`, `field`).

## Limitations

Only unrooted splits are compared; branch lengths and root position are ignored.
