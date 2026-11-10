# Causal forest feature importance

## Purpose

Fits a CausalForestDML on a table with an outcome, a binary treatment and covariates, then reports how much
each covariate contributes to treatment-effect heterogeneity.

## Inputs

One 2D form with named columns. `y_column` and `t_column` are removed from the design; the remaining columns
are covariates.

## Parameters

- `y_column`, `t_column`: outcome and treatment column names.
- `n_estimators`, `min_samples_leaf`: forest size and leaf constraint.
- `seed`: random state.

## Outputs

Two columns per covariate: `importance` (econml forest importance) and `share` (importance divided by its sum).

## Limitations

Requires `econml>=0.15,<0.16`, `scikit-learn>=1.4`, `numpy>=1.24`. Importances describe heterogeneity, not
causal identification; unconfoundedness and overlap are assumed. Binary treatment only.
