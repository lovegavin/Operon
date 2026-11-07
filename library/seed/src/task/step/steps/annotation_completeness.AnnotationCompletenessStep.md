# Annotation completeness

## Purpose

Marker completeness per genome from presence and copy counts.

## Inputs

A two-dimensional form with a `observation` row axis and a `field` column
axis. Required columns are validated at run time; non-finite values are
rejected.

## Parameters

`observation_dim` and `field_dim` name the two axes, and `output` names the
step result.

## Output

A numeric form with dimensions `[observation, statistic]`. See the
parameters schema for the exact statistic columns.

## Interpretation

Statistics are computed per observation from the supplied table only; no
reference annotation or external database is queried.

## Limitations

The operator is a table summary. It does not validate gene models, resolve
isoforms, or replace a full annotation-quality pipeline.

## Source

Generated alongside the operator implementation.
