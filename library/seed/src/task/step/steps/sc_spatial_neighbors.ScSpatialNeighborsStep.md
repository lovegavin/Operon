# Spatial k-nearest-neighbour graph

## Purpose

Build a Gaussian-weighted spatial kNN graph from cell coordinates.

## Inputs

Form table with a row label column and numeric fields.

## Parameters

- `k` (default 6)

## Limitations

Coordinates must share one scale; k-means is deterministic farthest-first and is not a full Leiden/SpaGCN model.
