# Spatially variable genes (Moran's I)

## Purpose

Score each gene with Moran's I on a spatial kNN graph.

## Inputs

Form table with a row label column and numeric fields.

## Parameters

- `k` (default 6)

## Limitations

Coordinates must share one scale; k-means is deterministic farthest-first and is not a full Leiden/SpaGCN model.
