# Uplift T-learner

## Purpose

Fit separate least-squares outcome models per treatment arm and report per-sample uplift.

## Parameters

See `uplift_t_learner.UpliftTLearnerStep.parameters.json`; `row_dim` and `field_dim` name the input axes.

## Limitations

Deterministic closed-form implementation on the stated inputs; no model training or parameter estimation beyond least squares / linear programming.
