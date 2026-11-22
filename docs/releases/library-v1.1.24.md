# library main-v1.1.24

Released 2026-11-23 with Operon Studio 5.7.38.

## Added

- **`ValuesReader`** — reads a single column of numbers (`.values`, `.vals`) and
  returns a one-dimensional form with `info.missing_code` and `info.n_values`.
  Parameters: `header` (boolean, default `false`), `comment` (string, default
  `#`), `column` (integer, default `0`).
  This is the first reader in the catalogue that produces a 1-D form, so
  `diversity_simpson` (`abundance_dim`) and `numeric_gini_coefficient`
  (`value_dim`) can finally be wired into a workflow. Before this release both
  were rejected at submission with `输入输出契约不兼容：需要 1 维数据`, because
  all 108 readers declared `ndim: 2` or `ndim: 3`.

## Fixed

- **Repeated VCF sites no longer lose their labels.** `vcf_hardy_weinberg` and
  `vcf_site_missingness` built row labels as `CHROM:POS`; two records at the same
  position collided, `Form` reported unlabeled positions and `subset_axis()`
  refused to run. `_vcf_qc_utils.site_labels()` keeps the first occurrence as
  `21:100` and suffixes later ones (`21:100#2`, `21:100#3`), so the axis stays
  complete.

## Registry

`python3 -m operon registry build --scope routes` reports
`1074 operators / 109 readers / 79 routes / 0 errors`.
