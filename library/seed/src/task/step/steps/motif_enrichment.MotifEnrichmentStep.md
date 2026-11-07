# motif_enrichment

Tests whether a motif occurs more often in foreground than in background sequences.

## Semantics

- A sequence is positive when it contains the motif as a case-insensitive substring.
- The 2x2 table `[[fg_hit, fg_miss], [bg_hit, bg_miss]]` is tested with a one-sided Fisher exact
  test (alternative `greater`).
- `fold` is the ratio of hit fractions; `odds_ratio` and `p_value` come from SciPy.

## Parameters

- `motif`: literal motif, for example `ACGTTGCA`.

## Limits

Substring matching ignores mismatches, reverse complements and composition bias. Small backgrounds
give unstable odds ratios; sequences are assumed independent.
