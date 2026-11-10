# LightGBM binary classifier

Fit a deterministic LightGBM gradient-boosted classifier and report training diagnostics.

## Purpose

Implements `lightgbm_classifier` for protocol 3.7 workflows.

## Inputs

One `form` table (row x field).

## Parameters

See `lightgbm_classifier.LightgbmClassifierStep.parameters.json`.

## Dependencies

`lightgbm>=4.0,<5`; the tested runtime version is recorded in the batch evidence.

## Limitations

Training-set diagnostics only; synthetic route data.
