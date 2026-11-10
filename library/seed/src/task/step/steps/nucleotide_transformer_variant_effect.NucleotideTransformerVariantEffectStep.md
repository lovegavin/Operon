## Purpose
Compare reference and alternate sequence windows in Nucleotide Transformer embedding space.

## Inputs
A table with `ref_column` and `alt_column` nucleotide windows.

## Outputs
Per variant: reference/alternate embedding norms, cosine similarity, Euclidean distance,
and the difference of norms.

## Dependencies
`torch>=2.4,<3`, `transformers>=4.50,<5`, plus the v2 50M weights.

## Limitations
Embedding-space distance is not a calibrated functional effect; identical windows are the
only exact control (cosine 1, distance 0). Windows are truncated at `max_length`.
