# peak_peak_distance

## Purpose

For every peak, reports the distance from its midpoint to the closest other midpoint.

## Semantics

- The output has one row per peak, with `nearest_distance` in base pairs and `nearest_index`.
- The diagonal of the pairwise distance matrix is excluded, so a peak is never its own neighbour.

## Parameters

- `row_dim` / `field_dim`: input dimension names.

## Limits

O(n^2) memory and time, intended for thousands of peaks. Ignores chromosome identity: peaks on
different chromosomes are compared by coordinate unless the caller pre-splits the table.
