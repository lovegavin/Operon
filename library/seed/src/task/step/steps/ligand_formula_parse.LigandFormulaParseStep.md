# Ligand formula parse

## Purpose

Element counts, heavy-atom and total-atom counts parsed from a Hill molecular formula.

## Inputs

One 2D Form whose `info["formula"]` list holds a Hill formula per molecule row
(for example the output of `ligand_molecular_formula`). Strings are parsed with a
strict element/count grammar; parentheses and charges are not supported.

## Parameters

`molecule_dim`, `field_dim` (input axis names) and `output` (workflow value name).

## Output

A 2D Form with dims `[molecule, statistic]` and the statistics
("C", "H", "N", "O", "P", "S", "F", "Cl", "Br", "I", "other_atoms", "heavy_atoms", "total_atoms", "distinct_elements"). Values are float32; formulas are echoed in `info["formula"]`.

## Interpretation

"elements": [dict(sorted(elements.items())) for elements in counts],

## Limitations

Only neutral, closed-shell Hill formulas without hydrate dots, charges or
parentheses are accepted. An element outside the periodic table raises a
`StepError` rather than being skipped.
