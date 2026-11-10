# Gene overlap check

## Purpose

Count pairwise overlaps between gene intervals in one table.

## Inputs

A two-dimensional form with a `gene` row axis and a `field` column
axis. Required columns are validated at run time; non-finite values are
rejected.

## Parameters

`gene_dim` and `field_dim` name the two axes, and `output` names the
step result.

## Output

A numeric form with dimensions `[gene, statistic]`. See the
parameters schema for the exact statistic columns.

## Interpretation

Statistics are computed per gene from the supplied table only; no
reference annotation or external database is queried.

## Limitations

The operator is a table summary. It does not validate gene models, resolve
isoforms, or replace a full annotation-quality pipeline.

## Source

Generated alongside the operator implementation.
