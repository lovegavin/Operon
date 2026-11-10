# HDBSCAN density clustering

Cluster a numeric table with HDBSCAN and return per-point cluster, probability and outlier score.

## Purpose

Implements `hdbscan_cluster` for protocol 3.7 workflows.

## Inputs

One `form` table (row x field).

## Parameters

See `hdbscan_cluster.HdbscanClusterStep.parameters.json`.

## Dependencies

`hdbscan>=0.8,<1`; the tested runtime version is recorded in the batch evidence.

## Limitations

Training-set diagnostics only; synthetic route data.
