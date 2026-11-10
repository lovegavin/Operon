# Score rows with a bottleneck autoencoder

Trains a small autoencoder (torch) and reports reconstruction-error statistics plus a mean+3sd anomaly threshold.

## Purpose

Part of the b85 torch batch; deterministic CPU training with a fixed seed.

## Parameters

`hidden` (default 12), `epochs` (200), `learning_rate` (0.05), `seed` (7).

## Limitations

Small fully-connected networks only; no GPU path and no validation split.
