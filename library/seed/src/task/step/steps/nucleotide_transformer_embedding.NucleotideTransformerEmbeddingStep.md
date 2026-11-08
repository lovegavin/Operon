## Purpose
Compute mean-pooled embeddings with the Nucleotide Transformer v2 50M multi-species model.

## Inputs
A two-dimensional table with one nucleotide sequence per row in `sequence_column`.

## Outputs
A `sequence x embedding` matrix of 512 float values per sequence (rounded to 4 decimals).

## Parameters
- `sequence_column`, `max_length`, `batch_size`, `model_path`.

## Dependencies
`torch>=2.4,<3`, `transformers>=4.50,<5`. Weights:
`InstaDeepAI/nucleotide-transformer-v2-50m-multi-species` (about 223 MB, downloaded via hf-mirror).

## Limitations
CPU inference only. Sequences longer than `max_length` are truncated (k-mer tokens).
Mean pooling includes special tokens.
