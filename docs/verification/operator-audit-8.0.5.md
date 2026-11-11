# Operator audit 8.0.5

8.0.5 is a dependency-correctness patch over 8.0.4. The five-layer evidence
from 8.0.4 is retained in `verification/operator-audit-8.0.5/`. This patch was
verified with focused contract, composition, release, and route tests plus one
real structure route; the full suite was not rerun.

## Findings addressed

| id | severity | finding | fix |
| --- | --- | --- | --- |
| OL-01 | P0 | `pdbfixer>=1.9` resolved to 1.12.0, which requires OpenMM 8.2; the Python 3.11 image only has OpenMM 8.1.1 | dedicated `openmm81` Python 3.11 environment with `openmm==8.1.1`, `numpy==1.26.4`, and PDBFixer 1.9 from a pinned commit |
| OL-02 | P2 | interface core/paratope composition was not accepted on Studio 4.0.8 | `vhh_cdr_quantification` rerun: join and per-CDR aggregate both succeed |
| OL-03 | P2 | `export_results` hard-required hictkpy | already fixed in 8.0.3; CSV export verified in the 4.0.8 rerun |

## Implementation

- New isolated environment:
  `library/seed/operon/environments.json` -> `openmm81`, Python 3.11,
  `openmm==8.1.1`, `numpy==1.26.4`, `setuptools`, `wheel`, and PDBFixer 1.9
  under `no_build_isolation`.
- Five operators declare `resources.environment: "openmm81"` and use the
  normal `from pdbfixer import PDBFixer` import inside that interpreter:
  `interface_mmgbsa_delta`, `structure_interface_residue_energy`,
  `structure_openmm_energy`, `structure_openmm_md_rmsf`,
  `structure_openmm_md_stability`.
- `interface_alanine_scan` declares only `openmm==8.1.1`; it does not
  instantiate PDBFixer.
- No vendored PDBFixer directory and no shared-runtime NumPy/pandas pin.

## Targeted result

- `tests/test_interface_contracts.py`: 9 passed.
- Contract + composition + release + route tests: 40 passed in 111.16 s.
- Registry: 1063 operators, 108 Readers, 7 packages, 79 routes, 0 errors.
- `openmm81` probe: `resolve()` and `probe()` succeeded for `openmm`,
  `pdbfixer`, and `numpy`.
- MMGBSA route: 2.488 s, `Task finished`.
- `vhh_cdr_quantification`: join `(19, 8)`; aggregate 4 groups x 7 features;
  export succeeded.
- `structure_openmm_energy` route was stopped after nine minutes; it is not
  used as release evidence. The preparation path is covered by the MMGBSA
  route.

## Bundle verification

- Linux bundle: `Operon-Library-v8.0.5-Linux.operon-library.zip`
  sha256 `e3557adcddda2de82d12cc472e227a825c6ac972ddad2d696b08d3f7e90b558d`.
- Studio 4.0.7 official verification: **95 passed, 2 skipped, 7 deselected**,
  application 4.0.7, library 8.0.5, 1063 operators, 108 Readers,
  `passed: true` (`application-4.0.7.json`).
- Studio 4.0.8 source-tree route acceptance for OL-02 passed; the official
  bundle verifier is pinned to the minimum supported application 4.0.7.

## Non-library findings

`NOL-01` through `NOL-06` from the same online test are application, scheduler,
MCP, or staging issues. They are recorded in
`docs/verification/backend-issues-non-library-4.0.5.md` and are not changed by
this library release.
