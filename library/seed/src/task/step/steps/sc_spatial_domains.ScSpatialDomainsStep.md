# Spatial domain assignment

## Purpose

Assign spatial domains by k-means on coordinates and report neighbour purity.

## Inputs

Form table with a row label column and numeric fields.

## Parameters

- `k` (default 6)
- `n_domains` (default 3)
- `iterations` (default 50)

## Limitations

Coordinates must share one scale; k-means is deterministic farthest-first and is not a full Leiden/SpaGCN model.
