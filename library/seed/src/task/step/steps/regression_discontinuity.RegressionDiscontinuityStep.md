# Sharp regression discontinuity

Local linear sharp RD jump at a cutoff with a triangular window.

## Purpose

Implements `regression_discontinuity` as a self-contained causal-inference operator. The operator
reads one table Form, validates the required columns, computes the estimate and
returns a one-row numeric Form.

## Parameters

See the adjacent parameters JSON. Column parameters name fields of the input
table; `output` is injected by the engine.

## Limitations

This is a compact estimator intended for screening and teaching workflows, not
a replacement for a full causal-inference package. It assumes no unmeasured
confounding, correct functional form and, for RD, no manipulation of the
running variable.
