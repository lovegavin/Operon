# Simpson diversity

## Purpose

Computes Simpson diversity and three related summaries from an abundance vector: the probability that two individuals drawn independently with replacement belong to the same category, its inverse (effective number of categories), the evenness of the abundance distribution, and richness. These are descriptive diversity statistics of the supplied counts.

## Inputs

One numeric 1-D form whose single dim is `abundance_dim` (`"abundance"` by default). Entries are non-negative abundances or counts per category. Non-finite entries are dropped before the statistics are computed; zero entries are kept as absent categories.

## Outputs

One 2-D numeric form with dims `["entry", "statistic"]` and shape 1 x 4, so it can be concatenated with other statistic tables.

- The `entry` axis has the single label `simpson`.
- The `statistic` axis is labeled `simpson`, `inverse_simpson`, `evenness`, `richness`.

With p_i = x_i / sum(x): `simpson` = sum(p_i^2), `inverse_simpson` = 1 / simpson, `evenness` = inverse_simpson / richness, and `richness` = the number of entries strictly greater than zero. Values in the output table are rounded to nine decimal places by the shared table helper.

## Parameters

- `abundance_dim` (default `abundance`): name of the single axis of the input form.
- `output` (default `simpson_diversity`): context key that receives the output form.

## Limitations

All four columns are descriptive statistics of the supplied vector; they do not test hypotheses about community structure and say nothing about sampling effort. Simpson diversity is undefined for an empty or all-zero vector, in which case every column is returned as 0.0, including `inverse_simpson` and `evenness`. Because non-finite entries are dropped, richness and the total are computed on the remaining values only.

## Failure modes

- Raises `StepError` when no input form is supplied.
- Raises `StepError` when the input is not a 1-D form with dims `[abundance_dim]`.
- Raises `StepError` when any finite abundance is negative.
