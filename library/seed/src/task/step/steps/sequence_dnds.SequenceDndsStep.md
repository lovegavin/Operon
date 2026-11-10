# dN/dS ratio (Nei-Gojobori)

## Purpose

Computes pairwise synonymous and non-synonymous substitution rates with the Nei-Gojobori site-counting method and Jukes-Cantor correction, reporting dN, dS and their ratio.

## Inputs

One form table with rows of coding sequences and columns of codons.

## Output

Two-column table (entry, statistic) with the operator metrics.

## Limitations

The implementation works on small alignments, treats stop codons as
non-synonymous and does not model gap characters.
