# RealNVP normalizing flow density

RealNVP affine-coupling flow trained by maximum likelihood on a 2-D table, reporting latent Gaussianity and parameters.

## Purpose

RealNVP affine-coupling flow trained by maximum likelihood on a 2-D table, reporting latent Gaussianity and parameters. The operator trains on the supplied table with a fixed seed and returns summary
statistics on a single output row.

## Inputs

- `input1`: table

## Parameters

- `k`: 2
- `k`: 8
- `k`: 300
- `k`: 0.05
- `k`: 0

## Outputs

- `output`: `form` with dims `entry` x `statistic`.

## Dependencies

`numpy>=1.24` (tested 2.1.3), `torch>=2.4,<3` (tested 2.11.0+cu130, CPU).
