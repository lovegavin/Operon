# Outgroup rooting

Re-roots a Newick tree on the terminal branch of `outgroup`. The output
row reports the tip count, root degree and the outgroup branch length;
the rooted Newick string is stored in `info.newick`.

## Purpose

Produce an outgroup-rooted topology for downstream display or
comparison.

## Parameters

- `row_dim`, `field_dim`: dims of the Newick table (column `newick`).
- `outgroup`: tip name to root on.
- `output`: output parameter name.

## Limits

- Rooting is topological; branch lengths outside the outgroup edge are
  preserved but not rescaled.
- Duplicate tip names are not supported.
