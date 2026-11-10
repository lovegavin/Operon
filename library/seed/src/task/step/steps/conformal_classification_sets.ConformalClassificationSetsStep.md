# Split conformal prediction sets for binary classification

## Purpose

Split-conformal binary prediction sets with a calibrated score threshold.

## Inputs

A numeric table whose columns are consumed positionally; the first column is the row label when the reader drops it.

## Parameters

See the adjacent parameter JSON. Dimensions default to `row`/`field`.

## Limitations

Synthetic or small tabular inputs are intended for deterministic verification; this is not a replacement for a full probabilistic-programming workflow.
