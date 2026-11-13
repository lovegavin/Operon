# Fork1 Gini coefficient

## Purpose

A small, self-contained operator used to test multi-library coexistence. It
summarizes a non-negative numeric vector with the Gini coefficient, count,
total and mean.

## Inputs

One numeric 1-D form whose single dim is `value_dim` (`"value"` by default).

## Outputs

One 2-D numeric form with dims `["entry", "statistic"]`, shape 1 x 4. The
`entry` axis has the label `fork1_numeric_gini`; the `statistic` axis is
labeled `gini`, `n`, `total`, `mean`.

## Parameters

- `value_dim` (default `value`): name of the input axis.
- `output` (default `fork1_gini`): context key receiving the output form.

## Limitations

Descriptive statistic only; no biological interpretation. Non-finite values
are dropped, so `n` can be smaller than the input length.

## Failure modes

- Raises `StepError` when no input form is supplied.
- Raises `StepError` when the input is not 1-D with dims `[value_dim]`.
- Raises `StepError` when a finite value is negative.
