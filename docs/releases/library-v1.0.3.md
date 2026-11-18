# Operator library main 1.0.3

Library version `1.0.3` accompanies Operon Studio `5.6.4`. It keeps the
`main` operator set (7 packages, 1,069 operators, 108 Readers, 1,177
descriptors) and stays compatible with applications `>= 5.6.2`.

## Changes since 1.0.2

- **Fetch robustness.** `resource_fetch.download` no longer assumes a
  `headers` attribute on the HTTP response object. The announced length falls
  back to `0` when a test double or an alternative transport omits headers,
  so checksum verification and atomic moves work for every transport. This
  fixes `AttributeError: '_Response' object has no attribute 'headers'`.
- **Version metadata.** `library/release.json`, the builtin package index and
  `library/pyproject.toml` now agree on `1.0.3`, so the independently
  versioned factory wheel reports the same version as the packaged library.

## Contents

- `operon-core`, `operon-expression`, `operon-genetics`, `operon-hic`,
  `operon-microbiome`, `operon-plots`, `operon-readers`
- 16 resources declared with one official maintenance unit each, 18 declared
  isolated environments, and a complete operator-to-environment assignment map.

## Verification

- `tests/test_resource_fetch.py`, `tests/test_resource_unit_download.py` and
  the resource suite pass on the release tree (`57 passed, 1 skipped` plus the
  unit download cases).
- The packaged library loads in a clean install as `main-v1.0.3` with
  1,177 descriptors and no missing environment stamps.
