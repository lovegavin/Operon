# InterPro domain summary

## Purpose

Per-protein domain count, covered bases and best e-value.

## Inputs

A two-dimensional form with a `hit` row axis and a `field` column
axis. Required columns are validated at run time; non-finite values are
rejected.

## Parameters

`hit_dim` and `field_dim` name the two axes, and `output` names the
step result.

## Output

A numeric form with dimensions `[hit, statistic]`. See the
parameters schema for the exact statistic columns.

## Interpretation

Statistics are computed per hit from the supplied table only; no
reference annotation or external database is queried.

## Limitations

The operator is a table summary. It does not validate gene models, resolve
isoforms, or replace a full annotation-quality pipeline.

## Source

Generated alongside the operator implementation.
