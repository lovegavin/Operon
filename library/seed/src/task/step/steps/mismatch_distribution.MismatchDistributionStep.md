# Mismatch distribution

## Purpose

Builds the pairwise mismatch distribution and reports its mean, variance, mode and Harpending raggedness index.

## Inputs

One form table with rows of individual sequences and columns of alignment sites.

## Output

Two-column table (entry, statistic) with the operator metrics.

## Limitations

The implementation works on small alignments, treats stop codons as
non-synonymous and does not model gap characters.
