# Filter proteins by missing-value fraction

Missing-value filtering drops proteins that are absent or
zero in too many samples.

The missing fraction counts non-finite and non-positive entries per protein.
Only proteins at or below `max_missing_fraction` are kept; counts are written
to `info`.

Limitations: filtering at a fixed fraction can bias downstream comparisons
when missingness is group-specific; consider group-wise missingness before
using the default.

## Source

`ms_missing_filter.py`
