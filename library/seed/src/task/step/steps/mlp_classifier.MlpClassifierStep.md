# Train a small MLP classifier

Fits a two-layer perceptron (torch) on a labelled feature table and reports training accuracy and cross-entropy loss.

## Purpose

Part of the b85 torch batch; deterministic CPU training with a fixed seed.

## Parameters

`hidden` (default 12), `epochs` (200), `learning_rate` (0.05), `seed` (7).

## Limitations

Small fully-connected networks only; no GPU path and no validation split.
