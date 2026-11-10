## Purpose

Builds a deterministic isolation forest from random splits and scores every row by expected path length.

## Parameters

- `n_estimators` (default `100`)
- `sample_size` (default `64`)
- `seed` (default `7`)
- `threshold` (default `0.6`)

## Inputs

A 2-D table of numeric values.

## Outputs

A table with one row per input row (or per forecast step) and one column per reported statistic.

## Limitations

- Rows are processed in the order supplied; no automatic sorting for anomaly operators.
- Floating-point outputs are rounded to nine decimals; cross-host byte equality is not guaranteed for all libm versions.
