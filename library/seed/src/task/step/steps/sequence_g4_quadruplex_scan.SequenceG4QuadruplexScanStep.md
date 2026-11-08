## Purpose
Scan sequences for G-quadruplex-like tracts: at least `min_tracts` runs of `min_g` guanines
separated by loops of at most `max_loop` non-G bases.

## Outputs
`n_g4`, `max_span`, and `max_g_tract` per sequence.

## Limitations
This is a sequence motif proxy, not a thermodynamic or structural G4 prediction.
