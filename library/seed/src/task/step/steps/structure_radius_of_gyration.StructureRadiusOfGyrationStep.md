# Radius of gyration

## Purpose

Radius of gyration and maximum atom radius of a PDB structure.

## Inputs

- `atom`: atom
- `field`: field

## Output

A two-dimensional numeric `form`.  Each output row carries the per-entry
statistics named in its `statistic` axis; matrix outputs use a second sample
axis instead.

## Limitations

The operator accepts numeric tables only.  Negative values are rejected, and
the caller is responsible for any upstream filtering or normalisation.
