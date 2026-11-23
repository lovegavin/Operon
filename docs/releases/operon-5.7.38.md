# Operon Studio 5.7.38

Released 2026-11-23. Library: `main-v1.1.24`.

## Added

- **One-dimensional values reader.** `ValuesReader` (`.values`, `.vals`) reads one
  number per line and returns a one-dimensional form, which is the shape
  `diversity_simpson` and `numeric_gini_coefficient` declare. Until now no reader
  produced that shape, so both operators were unreachable from any workflow.
  `header`, `comment` and `column` are optional parameters.

## Fixed

- **`GET /api/v1/jobs` honours `limit`.** The endpoint accepted no `limit`
  argument and always returned the whole history; a small limit now trims the
  payload instead of transferring every job.
- **Distinct labels for repeated VCF sites.** `VcfReader` produced a `site` axis
  without labels whenever two records shared `CHROM:POS`, so
  `vcf_hardy_weinberg` and `vcf_site_missingness` failed with
  `Form: dim 'site' has unlabeled positions`. Repeated positions now keep a
  suffix (`21:100`, `21:100#2`, …) and both operators run.

## Library

`library main-v1.1.24` carries the two library-side changes above
(`ValuesReader`, VCF site labels). The application release notes and the library
release notes are kept separate; this release ships both.
