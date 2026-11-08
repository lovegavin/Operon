# Deep quantile regressor

Linear pinball-loss quantile regression trained with Adam, reporting the fitted slope and intercept.

## Purpose

Linear pinball-loss quantile regression trained with Adam, reporting the fitted slope and intercept. The operator trains on the supplied table with a fixed seed and returns summary
statistics on a single output row.

## Inputs

- `input1`: table

## Parameters

- `k`: x
- `k`: y
- `k`: 0.5
- `k`: 500
- `k`: 0.05
- `k`: 0

## Outputs

- `output`: `form` with dims `entry` x `statistic`.

## Dependencies

`numpy>=1.24` (tested 2.1.3), `torch>=2.4,<3` (tested 2.11.0+cu130, CPU).
