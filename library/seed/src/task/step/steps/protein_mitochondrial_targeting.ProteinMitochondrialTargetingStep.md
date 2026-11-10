# Protein mitochondrial presequence score

## Purpose

Score an N-terminal mitochondrial presequence from charge and amphipathic moment.

## Inputs

A two-dimensional sequence Form (`sequence` x `position`) with protein
`sequence_codes`; unknown residues are sanitized to X.

## Parameters

- `sequence_dim` (default `sequence`): row axis.
- `position_dim` (default `position`): column axis.
- `output`: output Form name.

## Output

A `[sequence, statistic]` Form with columns: `positive_residues`, `negative_residues`, `net_charge`, `hydrophobic_moment`, `targeting_score`.

## Interpretation

The columns are arithmetic descriptors or consensus motif counts. They are not
functional annotations and do not replace curated database evidence.

## Limitations

- Full UniProt sequences are used, including signal and propeptides.
- Motif scans use short consensus rules and can produce false positives.
- The charge curve uses standard pKa values and ignores local environment.

## Source

`library/seed/src/task/step/steps/protein_mitochondrial_targeting.py`
