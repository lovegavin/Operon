# JC69 tree likelihood

Parses one Newick tree and a nucleotide alignment (one column per
site), then computes the Felsenstein pruning log-likelihood under the
Jukes-Cantor 69 substitution model with the branch lengths given in the
tree. The output is a single [entry, statistic] row with the log
likelihood; `n_sites` and `n_taxa` are reported in `info`.

## Purpose

Score a fixed tree against aligned sequences without relying on an
external phylogenetics package.

## Parameters

- `tree_dim`, `field_dim`: dims of the Newick table (column `newick`).
- `taxon_dim`, `site_dim`: dims of the alignment matrix.
- `output`: output parameter name.

## Limits

- JC69 only (equal base frequencies, one rate); no rate heterogeneity.
- Branch lengths are fixed; the operator does not optimise them.
- Ambiguous bases and gaps are rejected.
