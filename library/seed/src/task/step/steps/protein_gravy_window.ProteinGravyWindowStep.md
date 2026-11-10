# Protein GRAVY sliding window

## Purpose

Summarize Kyte-Doolittle GRAVY over 9-residue windows.

## Inputs

A two-dimensional sequence Form (`sequence` x `position`) with protein
`sequence_codes`; unknown residues are sanitized to X.

## Parameters

- `sequence_dim` (default `sequence`): row axis.
- `position_dim` (default `position`): column axis.
- `output`: output Form name.

## Output

A `[sequence, statistic]` Form with columns: `gravy_mean`, `gravy_max`, `gravy_min`, `max_window_start`.

## Interpretation

The columns are arithmetic descriptors or consensus motif counts. They are not
functional annotations and do not replace curated database evidence.

## Limitations

- Full UniProt sequences are used, including signal and propeptides.
- `gravy_mean` is the per-residue Kyte-Doolittle mean of the full sequence; `gravy_max`/`gravy_min` come from 9-residue windows, so terminal residues contribute only to the mean.

## Source

`library/seed/src/task/step/steps/protein_gravy_window.py`
