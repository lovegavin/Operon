# Operon Studio 5.7.21

5.7.21 fixes five defects found while driving environment installs from the
panel: a dependency row that could not be installed on its own, a 500 from
`GET /api/jobs/{id}` for environment jobs, misparsed PEP 427 dist-info names, a
remote log route that ran the retry handler, and AlphaFold2 readiness that
ignored missing files.

## Fixed

- F-133: installing one dependency from a row failed with `dependency kind
  'wheel' cannot be installed one by one`. Rows are labelled with display kinds
  (`wheel`, `pypi`, `conda`) but requirements live in buckets named
  `pip_wheels`, `pip_pypi` and `conda_packages`; `_KIND_ALIASES` maps them
  before validation, and a request without a kind infers it from the row, so
  all six buckets (`pip_wheels`, `pip_pypi`, `conda_packages`, `requirements`,
  `no_deps`, `no_build_isolation`) install one by one.
- F-134: `GET /api/jobs/{id}` answered 500 for a prepare or dependency job. The
  environment queue kept its dict closure-local, so the run-job lookup raised;
  it now publishes `app.state.environment_jobs`, and the route returns that job
  or 404 `unknown_job`.
- F-135: installed-version detection misread PEP 427 names;
  `torch_geometric-2.4.0.dist-info` parsed as project `torch`, version
  `geometric`. `metadata_name()` splits dist-info at the first hyphen and
  legacy egg-info at the first segment that starts with a digit.
- F-136 (P0): `GET /api/remote/{key}/environments/{name}/log` ran the retry
  handler, so reading a log restarted the install. The decorators are
  reordered; the GET serves the log, and a 404 for an unknown environment no
  longer starts a job.
- F-137: AF2 readiness trusted the unit state alone. It now follows
  `files_missing`: a unit with missing files reports `partial`, and an
  environment with such a gap is downgraded to `incomplete` with the Chinese
  reason (`资源未齐备（n/m）：unit`).

## Changed

- `/api/resources` reports `files_present` and `files_missing` per unit,
  resolved against the resource root or the link target.

## Verification

- `check95.py` 34/34 PASS; ready 64.5 s after launch and serving
  `5.7.21 (e7a202b9)`; library `main-v1.1.13` (1,074 operators, 1,182
  descriptors, 7 packages, 108 readers); 18 environments; MCP 141 tools.
- Sizes and digests are in `docs/releases/operon-5.7.21-test-report.md`.

## Known limitations

- A unit that ships without a declared file list cannot report `files_missing`;
  its card keeps the `未校验` state.
