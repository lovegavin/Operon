# Operator library fixes for the 4.2.0 task1 reports

Date: 2026-11-13

Scope: library issues OL-01, OL-02 and OL-03 from
`operator_library_issues_420.md`. Non-library issues NOL-01..NOL-05 are
reported separately and are not claimed as fixed here.

## OL-01: interface_alanine_scan magnitude and copy flags

`interface_alanine_scan` now declares five output columns:

| column | meaning |
| --- | --- |
| `wt_delta_kj` | wild-type single-point MM/GBSA delta |
| `mutant_delta_kj` | mutant single-point MM/GBSA delta |
| `delta_delta_kj` | mutant minus wild type |
| `excluded` | 1 when the absolute `delta_delta_kj` exceeds `max_delta_kj` |
| `replicate_conflict` | 1 when independent binder copies disagree in sign |

The default `max_delta_kj` is 50 kJ/mol. The value is a quality threshold, not
a physical cutoff: it does not alter `delta_delta_kj`. `info` records
`n_excluded`, `n_replicate_conflicts`, `flag_codes` and the threshold.

Real 1MEL binder-side G55 Gly-to-Ala scan (20 interface residues, three
independent runs of the same code) produced:

| run | A delta_delta (kJ/mol) | B delta_delta (kJ/mol) |
| --- | ---: | ---: |
| 1 | 1310.245 | 198.361 |
| 2 | 1104.541 | 127.420 |
| 3 | 1270.192 | 252.719 |

All values are above the 50 kJ/mol flag threshold. The run-to-run spread is
itself evidence that single-point MM/GBSA deltas at this interface are not a
quantitative affinity measurement. The report's `max_delta_kj` acceptance
case is therefore covered for both copies, with the threshold documented as a
quality flag.

## OL-02: copy-replicate agreement

`copy_replicate_quality` now reports Pearson, Spearman and sign-conflict
fraction for each pair of binder copies, excludes rows above the magnitude
threshold before correlating, and flattens the first pair's statistics into
`info["quality"]` when one pair exists. A warning is emitted when Spearman is
below 0.5 or sign conflicts exceed 20%. The 1MEL runs above gave Pearson
0.246-0.323 and Spearman 0.190-0.250 across copies, reproducing the report's
finding that copy-level hotspots are not reproducible. The operator does not
claim affinity or hotspot ranking.

## OL-03: interface_mmgbsa_delta protocol metadata

`interface_mmgbsa_delta` now emits:

- `protocol_id`: SHA-256 prefix of force field, implicit solvent, pH and
  single-point mode;
- `delta_terms`: the four component deltas as a mapping;
- `cancellation_ratio`: `(|nonbonded| + |GB|) / |total|`;
- `comparison_requires_identical_protocol: true`;
- `side_definition`;
- a warning when large nonbonded and GB terms oppose each other.

The numeric values are unchanged. The metadata makes the report's A-L
`-1.233 kJ/mol` (nonbonded `-1495.333`, GB `+1494.098`) visibly a cancellation
result and prevents comparing deltas from different protocols or sides.

## Verification

Commands run in `/home/gavin/Operon-405` with the library Python:

```text
pytest -q tests/test_extension296.py tests/test_extension297.py \
  tests/test_extension298.py tests/test_interface_contracts.py \
  tests/test_library_release.py tests/test_contract_compositions.py
41 passed, 1 skipped in 80.13s
```

The skip is `test_real_mmgbsa`, which requires the `openmm81` isolated
environment in this Python. The G55 scan above was run with an OpenMM 8.1.1 / PDBFixer 1.9
environment; the separate 4.1.9 environment installation and PDBFixer probe was
recorded in the 8.0.8 acceptance evidence, not as a rerun of this test.

Registry build and package refresh completed; `registry check --json` reports
0 errors.

## Non-library issues

NOL-01 (workspace ACL), NOL-02 (MCP CSV read/capability), NOL-03
(`artifact_table` row cap), NOL-04 (job wait timeout) and NOL-05 (remote profile
unavailable) remain application-side. No library workaround or fabricated
verification is claimed for them.
