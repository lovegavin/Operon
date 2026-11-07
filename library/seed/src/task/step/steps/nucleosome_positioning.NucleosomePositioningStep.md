# nucleosome_positioning

Estimates the dominant repeat length of a signal track (for example MNase-seq coverage) through
autocorrelation.

## Semantics

- The track is mean-centred and `r(lag) = sum(x[:-lag] * x[lag:]) / sum(x*x)`.
- The lag with the largest positive correlation between `min_lag` and `max_lag` gives
  `period_bp = lag * step_bp`.
- Output rows: `period_bp`, `strength`, `best_lag`, `n_lags`, `step_bp`.

## Parameters

- `step_bp` (default 10): base pairs per sample.
- `min_lag` (default 10), `max_lag` (default 40): lag window in samples.

## Limits

Assumes evenly spaced samples; no detrending of slow coverage waves and no individual nucleosome
calls. Noisy tracks can produce spurious maxima. Requires more samples than `max_lag`.
