# Dinucleotide frequency

## Purpose

Counts every overlapping dinucleotide in the ACGT content of one or more nucleotide sequences and derives three statistics per dinucleotide: the raw count, the frequency over all dinucleotide windows, and the CpG observed/expected ratio. The operator describes sequence composition; it does not infer biological function.

## Inputs

One sequence form: a 2-D numeric form whose dims are `[sequence_dim, position_dim]` (`["sequence", "position"]` by default). Rows are sequences, columns are aligned positions, and the form must carry `info["representation"] == "sequence_codes"` with an `info["alphabet_map"]` so positions can be decoded back to letters. Rows terminate at the first missing position.

## Outputs

One 2-D numeric form with dims `["dinucleotide", "statistic"]` and shape 16 x 3.

- The `dinucleotide` axis is labeled in the fixed order AA, AC, AG, AT, CA, CC, CG, CT, GA, GC, GG, GT, TA, TC, TG, TT.
- The `statistic` axis is labeled `count`, `frequency`, `cpg_observed_expected`.
- `frequency` values sum to 1 over the 16 dinucleotides whenever at least one window exists.
- `cpg_observed_expected` is filled for the CG row only; the other rows are 0.0.
- `info` carries `n_sequences`, `n_windows`, `n_bases` and the scalar `cpg_observed_expected`.

## Parameters

- `sequence_dim` (default `sequence`): name of the sequence axis of the input form.
- `position_dim` (default `position`): name of the position axis of the input form.
- `output` (default `dinucleotide_frequency`): context key that receives the output form.

## Limitations

All three columns are descriptive statistics of the supplied sequences. Dinucleotide frequencies are strand-agnostic: each sequence is analyzed in the orientation it is given, without reverse-complement aggregation. Windows overlap (a sequence of length L contributes L-1 windows), and only A, C, G and T characters are counted: characters outside that alphabet are dropped before windows are counted, so a window can span a dropped character. CpG observed/expected is computed as freq(CpG) / (freq(C) * freq(G)) over the same filtered letters and is not a test of statistical significance.

## Failure modes

- Raises `StepError` when no input form is supplied.
- Raises `StepError` when the input dims are not exactly `[sequence_dim, position_dim]`.
- Raises `StepError` when the form cannot be decoded as sequence codes (missing representation or alphabet map).
- Returns all-zero counts and frequencies, and 0.0 for CpG observed/expected, when the filtered sequences contain fewer than two ACGT letters.
