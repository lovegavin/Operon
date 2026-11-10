# Bayesian linear regression

Gibbs sampling for a normal-inverse-gamma linear model with weakly informative priors.

## Purpose

Implements `bayesian_linear_regression` as a self-contained Bayesian estimator. The
operator reads one table Form, treats the configured outcome and covariate columns
as numeric fields, runs a Gibbs sampler over the regression coefficients and the
residual variance, and returns one row per parameter with posterior mean, standard
deviation, credible interval and the posterior mean of sigma squared.

## Parameters

`y_column` and `covariate_columns` (comma separated) select the model columns.
`n_samples` and `burn_in` control the chain length, `prior_scale` the coefficient
prior, and `shape`/`scale` the inverse-gamma prior on sigma squared. `seed` makes
the sampler reproducible. `row_dim`/`field_dim` name the input axes and `output`
is injected by the engine.

## Output

A Form with one row per parameter (`(Intercept)` and each covariate) and columns
`mean`, `sd`, `ci_low`, `ci_high` and `sigma2`.

## Limitations

The sampler assumes independent Gaussian errors and a linear mean. It is intended
for screening and teaching, not for model selection or hierarchical structure.
