## Purpose

Computes k-distance, local reachability density and the local outlier factor for every row.

## Parameters

- `k` (default `5`)
- `threshold` (default `1.5`)

## Inputs

A 2-D table of numeric values.

## Outputs

A table with one row per input row (or per forecast step) and one column per reported statistic.

## Limitations

- Rows are processed in the order supplied; no automatic sorting for anomaly operators.
- Floating-point outputs are rounded to nine decimals; cross-host byte equality is not guaranteed for all libm versions.
