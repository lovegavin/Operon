# Ligand double-bond equivalents

## Purpose

Ring-plus-double-bond equivalents and their integrality from formula element counts.

## Inputs

One 2D Form whose `info["formula"]` list holds a Hill formula per molecule row
(for example the output of `ligand_molecular_formula`). Strings are parsed with a
strict element/count grammar; parentheses and charges are not supported.

## Parameters

`molecule_dim`, `field_dim` (input axis names) and `output` (workflow value name).

## Output

A 2D Form with dims `[molecule, statistic]` and the statistics
("dbe", "dbe_rounded", "integer_dbe", "halogen_count", "dbe_minus_halogen"). Values are float32; formulas are echoed in `info["formula"]`.

## Interpretation

"dbe_definition": "C - (H + X)/2 + N/2 + 1",

`dbe` is the standard ring-plus-double-bond count. `dbe_minus_halogen` applies
+1 as well and treats halogens as hydrogens, so it must equal `dbe` for a
neutral closed-shell formula; the column is a cross-check, not a second
definition. `integer_dbe` is 1 when `dbe` is an integer within 1e-9, otherwise 0.

## Limitations

Only neutral, closed-shell Hill formulas without hydrate dots, charges or
parentheses are accepted. An element outside the periodic table raises a
`StepError` rather than being skipped.
