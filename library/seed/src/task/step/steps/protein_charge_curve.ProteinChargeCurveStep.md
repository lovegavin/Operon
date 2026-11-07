# Protein charge versus pH

## Purpose

Compute the net charge at pH 3 to 11 using standard residue pKa values.

## Inputs

A two-dimensional sequence Form (`sequence` x `position`) with protein
`sequence_codes`; unknown residues are sanitized to X.

## Parameters

- `sequence_dim` (default `sequence`): row axis.
- `position_dim` (default `position`): column axis.
- `output`: output Form name.

## Output

A `[sequence, statistic]` Form with columns: `charge_ph3`, `charge_ph4`, `charge_ph5`, `charge_ph6`, `charge_ph7`, `charge_ph8`, `charge_ph9`, `charge_ph10`, `charge_ph11`.

## Interpretation

The columns are arithmetic descriptors or consensus motif counts. They are not
functional annotations and do not replace curated database evidence.

## Limitations

- Full UniProt sequences are used, including signal and propeptides.
- pKa values follow the ExPASy/EMBOSS convention: Nterm 8.6, Cterm 3.6, D 3.9, E 4.1, C 8.5, Y 10.1, H 6.5, K 10.8, R 12.5.
- Biopython/ProtParam uses a different pKa set (Nterm 7.5, K 10.0, R 12.0, H 5.98, D 4.05, E 4.45, C 9.0, Y 10.0), so absolute charges can differ by a few tenths.
- The curve ignores local environment, binding partners and post-translational charge changes.

## Source

`library/seed/src/task/step/steps/protein_charge_curve.py`
