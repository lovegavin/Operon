# Operon Library 7.0.9

Audit-evidence release for Studio 3.1.6. No operator behavior, protocol field,
route template or bundle format changed in this release.

## What changed

- Added 40 route fixtures (37 sequence-input plus 3 shared multi-input) to the audit evidence. These cover
  previously unverified operators that take `sequence_codes` forms: protein
  property scans, motif and signal-peptide scans, codon usage, restriction
  sites, GC/CPG profiles, translation, tRNA scan, antibody numbering/CDR
  metrics, VHH humanization and sequence liability scans.
- Route coverage in the audit record rises from 522/1063 to **562/1063**;
  501 operators remain without a passing route and are listed with their
  blocking reason in the per-operator table.
- The per-operator table (`operator_table.csv`, 1176 operator rows plus the
  header) now records the sequence-route replay for those operators.
- L2 independent numeric oracle coverage remains 13/13; L0 remains
  1171/1171 PASS; L1 remains 358 PASS / 0 FAIL with 587 domain SKIPs.

## Verification

- Full pytest: 3722 passed, 209 skipped, 0 failed (41:39).
- Clean Studio 3.1.6 bundle verify: `passed: true`, 1063 operators,
  108 readers, 95 focused tests passed, 2 skipped.
- `operon registry check --json`: 1063 operators, 0 errors, 79 route
  templates.
- Documentation `--check`: rc 0. Portability audit: 0 findings.
- The audit tables explicitly mark L2/L4/L5 as partial; unimplemented checks
  are `not_measured`, never inferred.

## Assets

The release publishes the Linux and Windows library bundles, the route
collection, the quickstart archive, the wheel, the operator-audit archive,
`SHA256SUMS.txt`, both verification JSON files, the bilingual quickstart
documents and the three dependency-install scripts.
