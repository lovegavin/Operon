# Ligand adduct m/z

## Purpose

Neutral monoisotopic mass and adduct-specific m/z for a Hill formula.

## Inputs

One 2D Form whose `info["formula"]` list holds a Hill formula per molecule row
(for example the output of `ligand_molecular_formula`). Strings are parsed with a
strict element/count grammar; parentheses and charges are not supported.

## Parameters

`molecule_dim`, `field_dim` (input axis names) and `output` (workflow value name).

## Output

A 2D Form with dims `[molecule, statistic]` and the statistics
("neutral_exact_mass", "adduct_delta", "charge", "mz"). Values are float32; formulas are echoed in `info["formula"]`.

## Interpretation

"adduct": adduct,

## Limitations

Only neutral, closed-shell Hill formulas without hydrate dots, charges or
parentheses are accepted. An element outside the periodic table raises a
`StepError` rather than being skipped.
