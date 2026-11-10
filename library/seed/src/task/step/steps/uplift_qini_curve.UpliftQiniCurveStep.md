# Uplift Qini curve

## Purpose

Sort samples by estimated uplift and report the cumulative Qini gain curve.

## Parameters

See `uplift_qini_curve.UpliftQiniCurveStep.parameters.json`; `row_dim` and `field_dim` name the input axes.

## Limitations

Deterministic closed-form implementation on the stated inputs; no model training or parameter estimation beyond least squares / linear programming.
