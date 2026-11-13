# Gini coefficient

## Purpose

Summarizes the inequality of a non-negative numeric vector with the Gini coefficient and reports the count, total and mean of the finite values. The Gini coefficient is a descriptive concentration measure; a value of 0 means all values are equal and larger values mean the mass is concentrated in fewer entries.

## Inputs

One numeric 1-D form whose single dim is `value_dim` (`"value"` by default). Values are interpreted as non-negative quantities. Non-finite entries (NaN and infinities) are dropped before the statistics are computed.

## Outputs

One 2-D numeric form with dims `["entry", "statistic"]` and shape 1 x 4, so it can be concatenated with other statistic tables.

- The `entry` axis has the single label `gini`.
- The `statistic` axis is labeled `gini`, `n`, `total`, `mean`.

`gini` is computed as sum_i sum_j |x_i - x_j| / (2 * n^2 * mean), which is evaluated with the sorted-rank identity sum_i (2i - n - 1) * x_(i) / (n * total) for speed. Values in the output table are rounded to nine decimal places by the shared table helper.

## Parameters

- `value_dim` (default `value`): name of the single axis of the input form.
- `output` (default `gini_coefficient`): context key that receives the output form.

## Limitations

The Gini coefficient is a descriptive statistic of the supplied values and carries no causal or biological interpretation. It is only defined for non-negative values with a positive mean; the implementation returns 0.0 for an empty vector or a zero mean. Because non-finite entries are dropped, `n` may be smaller than the input vector length.

## Failure modes

- Raises `StepError` when no input form is supplied.
- Raises `StepError` when the input is not a 1-D form with dims `[value_dim]`.
- Raises `StepError` when any finite value is negative.
