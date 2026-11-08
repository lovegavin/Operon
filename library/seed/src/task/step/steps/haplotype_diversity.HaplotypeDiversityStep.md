# Haplotype and nucleotide diversity

## Purpose

Counts distinct haplotypes and reports Nei's haplotype diversity, average pairwise nucleotide diversity and the number of segregating sites.

## Inputs

One form table with rows of individual sequences and columns of alignment sites.

## Output

Two-column table (entry, statistic) with the operator metrics.

## Limitations

The implementation works on small alignments, treats stop codons as
non-synonymous and does not model gap characters.
