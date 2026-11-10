# GTR tree likelihood

## Purpose

Felsenstein pruning log-likelihood for a fixed Newick tree and aligned nucleotide matrix under a general time-reversible model.

## Inputs

Tree table with a `tree` column, and an alignment with taxa as rows and sites as columns.

## Parameters

- `base_freqs`: comma-separated A,C,G,T frequencies summing to one.
- `rates`: six comma-separated exchangeabilities A-C,A-G,A-T,C-G,C-T,G-T.

## Limitations

Branch lengths and topology are fixed. The implementation assumes a reversible model and a single alignment.
