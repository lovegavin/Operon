# Train a small MLP regressor

Fits a two-layer perceptron (torch) on a feature table with a target column and reports RMSE, MAE and R2.

## Purpose

Part of the b85 torch batch; deterministic CPU training with a fixed seed.

## Parameters

`hidden` (default 12), `epochs` (200), `learning_rate` (0.05), `seed` (7).

## Limitations

Small fully-connected networks only; no GPU path and no validation split.
