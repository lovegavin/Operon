# iBAQ protein abundance

## Purpose

Per-protein iBAQ from peptide intensities: summed intensity divided by the number of observable peptides.

## Output

A two-dimensional numeric `form`.  Rows are entries (protein, sequence or
site) and columns are the per-entry statistics described by the `statistic`
axis labels.

## Limitations

Values must be non-negative where they represent intensities.  Missing or
zero denominators produce `nan` rather than an error so downstream filtering
can decide how to treat them.
