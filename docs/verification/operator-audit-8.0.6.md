# Operator library audit 8.0.6

Library 8.0.6 is the environment-distribution release for Studio 4.1.0 and
newer. It inherits the operator and five-layer audit of 8.0.5. The delta is
the environment manifest bundle contract, the runtime source-root binding, the
forward-minimum release gate and environment-proxy execution for operators
that declare `resources.environment`.

Studio 4.1.0 is released after this library. Its runtime acceptance is an
explicit post-release gate. The available 4.0.8 code line plus the 8.0.6
runtime changes was used for a compatibility check; stock 4.0.8 is not a
supported host because it predates environment-manifest import.

## Findings addressed

| id | severity | finding | fix |
| --- | --- | --- | --- |
| OL-01 | P0 | `pdbfixer>=1.9` resolved to 1.12.0, which requires OpenMM 8.2; the Python 3.11 image only provides OpenMM 8.1.1 | dedicated `openmm81` Python 3.11 environment with `openmm==8.1.1`, `numpy==1.26.4`, and PDBFixer 1.9 from a pinned commit |
| OL-02 | P2 | interface core/paratope composition was not accepted on Studio 4.0.8 | `vhh_cdr_quantification` rerun: join `(19,8)` and per-CDR aggregate `4 groups x 7 features` succeed |
| OL-03 | P2 | `export_results` hard-required hictkpy | already fixed in 8.0.3; CSV export verified in the 4.0.8 rerun |

## Implementation

- `library/seed/operon/environments.json` defines `openmm81`: Python 3.11,
  `openmm==8.1.1`, `numpy==1.26.4`, `setuptools`, `wheel`, and PDBFixer 1.9
  under `no_build_isolation`.
- Five operators declare `resources.environment: "openmm81"` and import
  `from pdbfixer import PDBFixer` inside that interpreter:
  `interface_mmgbsa_delta`, `structure_interface_residue_energy`,
  `structure_openmm_energy`, `structure_openmm_md_rmsf`,
  `structure_openmm_md_stability`.
- `interface_alanine_scan` declares only `openmm==8.1.1`; it does not
  instantiate PDBFixer.
- No vendored PDBFixer directory and no shared-runtime NumPy/pandas pin.

## Bundle and runtime contract

- `snapshot_sources()` includes `sources/operon/environments.json`.
- `unpack_bundle()` accepts exactly that file in addition to the operator,
  Reader, package and `builtin_packages.json` paths; unexpected files and path
  traversal are rejected.
- `build_bundle()` reads `minimum_application` from `library/release.json`
  instead of hard-coding it. This release declares `4.1.0`; the build
  application is `4.0.8`.
- `environments.manifest_path()` reads the active source library first and
  falls back to the application seed or wheel.
- Operators with `resources.environment` execute through `EnvironmentStep`.
  They do not fall back to the shared interpreter when the environment is
  missing; readiness reports the missing environment.

## Targeted result

- `tests/test_library_environment_manifest.py tests/test_library_release.py`:
  **12 passed in 12.00 s**.
- Contract, composition, release and route tests from 8.0.5: **40 passed in
  111.16 s**; the 8.0.6 delta adds the environment bundle tests.
- Registry: 1063 operators, 108 Readers, 7 packages, 79 routes, 0 errors.
- `openmm81` probe: `resolve()` and `probe()` succeeded for `openmm`,
  `pdbfixer`, and `numpy`.
- MMGBSA route: 2.488 s, `Task finished`.
- `vhh_cdr_quantification`: join `(19,8)`; aggregate 4 groups x 7 features;
  export succeeded.
- `structure_openmm_energy` route was stopped after nine minutes; it is not
  used as release evidence. The preparation path is covered by the MMGBSA
  route.

## Bundle verification

- Linux bundle: `Operon-Library-v8.0.6-Linux.operon-library.zip`
  sha256 `0cf2c2a648e5d1fb0d82c859e2de80d435ea3fa5be70fa71e9043e9764a05ea2`.
- The bundle contains `sources/operon/environments.json` (4247 bytes).
- 4.0.8 code line + 8.0.6 runtime changes: install, frozen routes, worker
  streaming, environment manifest import and environment probe
  **95 passed, 2 skipped, 7 deselected**, `passed: true`
  (`application-4.0.8-compat.json`). The verification copy changes only
  `minimum_application`; the bundle bytes are otherwise exact.
- Studio 4.1.0 runtime acceptance: **pending**.

## Non-library findings

`NOL-01` through `NOL-06` from the same online test are application, scheduler,
MCP, or staging issues. They are recorded in
`docs/verification/backend-issues-non-library-4.0.5.md` and are not changed by
this library release.
