# CRISPR MIT specificity

## Purpose

Compute the Hsu 2013 position-weighted MIT specificity score for guide/off-target pairs.

## Parameters

See `crispr_mit_specificity.CrisprMitSpecificityStep.parameters.json`; `row_dim` and `field_dim` name the input axes.

## Limitations

Deterministic closed-form implementation on the stated inputs; no model training or parameter estimation beyond least squares / linear programming.
