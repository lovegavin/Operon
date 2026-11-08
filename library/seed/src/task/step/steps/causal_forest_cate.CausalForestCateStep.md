# Causal forest conditional effects

## Purpose

Per-sample conditional average treatment effects with 95% confidence intervals.

## Inputs

One 2D form with named columns. `y_column` and `t_column` are removed from the feature design; every other
column is used as a covariate. Treatment is interpreted as binary (0/1).

## Parameters

- `y_column`, `t_column`: outcome and treatment column names.
- `n_estimators`, `min_samples_leaf`: causal-forest size and leaf constraint.
- `max_depth` (policy tree only): tree depth.
- `seed`: random state for the forest and the nuisance models.

## Outputs

Columns `effect,ci_low,ci_high`, one row per sample (ATE returns a single summary row).

## Limitations

Requires `econml>=0.15,<0.16`, `scikit-learn>=1.4` and `numpy>=1.24`. The forest is fit on the provided
sample only; overlap and unconfoundedness are assumed and not tested. Binary treatment only.
