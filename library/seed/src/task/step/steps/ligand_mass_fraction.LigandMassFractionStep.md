# Ligand element mass fraction

## Purpose

Average-mass fraction of each element in a Hill formula.

## Inputs

One 2D Form whose `info["formula"]` list holds a Hill formula per molecule row
(for example the output of `ligand_molecular_formula`). Strings are parsed with a
strict element/count grammar; parentheses and charges are not supported.

## Parameters

`molecule_dim`, `field_dim` (input axis names) and `output` (workflow value name).

## Output

A 2D Form with dims `[molecule, statistic]` and the statistics
("C", "H", "N", "O", "P", "S", "halogens", "other", "total_mass"). Values are float32; formulas are echoed in `info["formula"]`.

## Interpretation

"unit": "fraction of average molecular mass",

## Limitations

Only neutral, closed-shell Hill formulas without hydrate dots, charges or
parentheses are accepted. An element outside the periodic table raises a
`StepError` rather than being skipped.
