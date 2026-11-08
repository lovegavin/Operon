# GCN node classifier

Two-layer graph convolutional network for semi-supervised node classification on a synthetic homophilous graph.

## Purpose

Two-layer graph convolutional network for semi-supervised node classification on a synthetic homophilous graph. The operator trains on the supplied table with a fixed seed and returns summary
statistics on a single output row.

## Inputs

- `input1`: table
- `input2`: table

## Parameters

- `k`: label
- `k`: 8
- `k`: 300
- `k`: 0.05
- `k`: 0

## Outputs

- `output`: `form` with dims `entry` x `statistic`.

## Dependencies

`numpy>=1.24` (tested 2.1.3), `torch>=2.4,<3` (tested 2.11.0+cu130, CPU).
