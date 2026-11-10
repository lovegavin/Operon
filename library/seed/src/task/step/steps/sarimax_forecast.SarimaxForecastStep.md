## Purpose

Fits a SARIMAX model to an ordered series and returns a multi-step forecast with confidence bounds.

## Parameters

- `time_column` (default `time`)
- `value_column` (default `value`)
- `order_p` (default `1`)
- `order_d` (default `0`)
- `order_q` (default `0`)
- `steps` (default `3`)
- `alpha` (default `0.05`)

## Inputs

A 2-D table of numeric values.

## Outputs

A table with one row per input row (or per forecast step) and one column per reported statistic.

## Limitations

- Rows are processed in the order supplied; no automatic sorting for anomaly operators.
- Floating-point outputs are rounded to nine decimals; cross-host byte equality is not guaranteed for all libm versions.
