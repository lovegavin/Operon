# Kalman filter for a local-level state-space model

## Purpose

Local-level Kalman filter with filtered states and Gaussian log-likelihood.

## Inputs

A numeric table whose columns are consumed positionally; the first column is the row label when the reader drops it.

## Parameters

See the adjacent parameter JSON. Dimensions default to `row`/`field`.

## Limitations

Synthetic or small tabular inputs are intended for deterministic verification; this is not a replacement for a full probabilistic-programming workflow.
