# Library 8.0.9

Release date: 2026-11-13

## Compatibility

- **Minimum application: Studio 4.2.1**
- Built and compatibility-tested with Studio 4.2.1.
- Target-runtime acceptance: the final Linux bundle was installed into an isolated Studio 4.2.1 profile, the standard operator probe passed, and the install was idempotent. Evidence is recorded in `verification/operator-audit-8.0.9/application-4.2.1-compat.json`. The `openmm81` environment was validated from the source manifest on Studio 4.1.9; re-preparing it from the frozen bundle was not repeated for this release.
- Linux bundle SHA256: `91f11de9fa333f68381cfd7dc583eb7e70f289446c0265ebb2956c94c1b20b5f`.
- Windows bundle SHA256: `1ac24f24dc2b00185df1de9f844684806df947f0fa5fe781bfed1a0d003f8f22`.

## Fixes

### OL-01: fragile alanine-scan values are flagged

`interface_alanine_scan` now separates numerical quality from the raw energy
values:

- `excluded` marks `|delta_delta_kj| > max_delta_kj`; the default is
  `50 kJ/mol`. Raw values are never changed.
- `replicate_conflict` marks the same residue number when two copies of one
  side have opposite signs.
- `flag` combines both: `1` magnitude, `2` replicate conflict, `3` both.
- Output metadata adds `n_excluded`, `n_replicate_conflicts`, `flag_codes`,
  and per-mutation `excluded_reason`.
- `max_delta_kj` is an explicit parameter; the previous three-column output is
  extended to five columns.

On the 4.2.0 1MEL G55 case, three repeat runs gave binder-side values
1310.245 / 1104.541 / 1270.192 and 198.361 / 127.420 / 252.719 kJ/mol. All were
above the default threshold and are now marked rather than silently reported as
ranked hotspots.

### OL-02: copy-replicate agreement is reported

`interface_alanine_scan` quality metadata now includes Pearson as well as
Spearman and the sign-conflict fraction. Residues whose signs disagree between
two copies are marked `replicate_conflict=1` on both rows. A low-correlation or
high-conflict pair emits a warning and must not be interpreted as a validated
hotspot.

### OL-03: MM/GBSA protocol and cancellation are explicit

`interface_mmgbsa_delta` now publishes:

- `protocol_id`, a stable hash of force field, implicit model, pH and
  single-point mode;
- `delta_terms`, with the nonbonded, GB and total terms together;
- `cancellation_ratio = (|nonbonded| + |gb|) / |total|`;
- `comparison_requires_identical_protocol: true`.

When the nonbonded and GB terms have opposite signs and their absolute sum is
at least five times the net delta, a warning states that the small net value is
numerically fragile. The A-L 4.2.0 case (nonbonded -1495.333, GB +1494.098,
total -1.233 kJ/mol) now carries that warning. These values remain single-point,
entropy-free, non-ensemble and uncalibrated; they are not affinities.

## Verification

- Targeted tests: 41 passed, 1 skipped (the skipped test requires the
  `openmm81` environment).
- Registry: 1,063 operators, 108 readers, 7 packages, 79 routes, 0 errors.
- Documentation check: 0 errors.
- L5 target-runtime install acceptance: the bundle was installed and the
  standard probe passed; JSON evidence is
  `verification/operator-audit-8.0.9/application-4.2.1-compat.json`.
