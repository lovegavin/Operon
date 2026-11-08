# XGBoost regressor

Fit a deterministic XGBoost histogram regressor and report training diagnostics.

## Purpose

Implements `xgboost_regressor` for protocol 3.7 workflows.

## Inputs

One `form` table (row x field).

## Parameters

See `xgboost_regressor.XgboostRegressorStep.parameters.json`.

## Dependencies

`xgboost>=2.0,<4`; the tested runtime version is recorded in the batch evidence.

## Limitations

Training-set diagnostics only; synthetic route data.
