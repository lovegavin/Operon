# Operon Studio 5.7.33 test report

The release closes the second round of defects that the operator sweep found on
the Linux server, with evidence gathered from real routes (MCP submissions, real
public data, no synthetic placeholders).

## Measurements

| Item | Value |
| --- | --- |
| Remote jobs recorded | 1,147 (475 complete, 671 failed, 1 running) |
| Operators attempted | 589 of 1,074 |
| Operators completed at least once | 294 |
| Environments ready | 19 / 19 |
| Resources missing files | 0 (37 of 37 units reachable) |

## Defects fixed in this release

| Symptom | Root cause | Fix |
| --- | --- | --- |
| `structure_path is required` / `structure_path . is not a file` (5 ProteinMPNN operators) | the operator consumed the structure twice: as the atom form and as a repeated path parameter | `_protein_common.structure_file()` re-emits the form into a temporary PDB, like the DSSP operator already did |
| `model_path is required; point it at a local ESM-IF1 checkpoint` (7 `esm_if_*` operators) | the loader demanded a path although the resource declares the checkpoint | `_esm_if_common.default_checkpoint()` / `_esm_common.default_checkpoint()` resolve the resource root |
| `No module named 'pydantic'` (18 operators across `core`, `genomics`, `esm2`, `hmmer`, `dssp`, ...) | `operon.plugins` imports `operon_sdk.protocol`, which imports `pydantic`, so any environment without it fails before the operator runs | every environment declares `pydantic>=2.7` |
| `hmmer_domains: No module named 'numpy'` | `hmmer` declared no Python requirements at all | `hmmer` declares `numpy>=1.24` |
| `amrfinder_plus: Database requires software version at least 4.2.0` | the resource points at the current NCBI database while the environment pinned `ncbi-amrfinderplus=3.12` | `antismash` pins `ncbi-amrfinderplus=4.2.5` |

## Evidence

- `iris.csv` → `pca`: complete in 16.8 s (`exec-3a7273794fb84abab1d28eb13f99c1cc`) after the
  `CsvReader` label rule was written correctly (`labels: {"sample": {"feature": 0}}`).
- FASTA family: after `918414f97` the `unsupported label rule for 'position': 'builtin'`
  error disappeared from all 108 replayed cases; the remaining failures are fixture
  semantics (single-sequence operators fed a 20,429-record FASTA), not reader defects.
- `esm2` resource: `load_model_and_alphabet_local` now loads
  `esm2_t6_8M_UR50D.pt` together with the 1,511-byte
  `esm2_t6_8M_UR50D-contact-regression.pt` head that fair-esm requires.

## Known gaps

- `vina==1.2.5` is the only optional binding that cannot be installed (no cp311
  wheel; the source build fails).
- The shared-pool version gate still surfaces as an operator failure
  (`Another Operon version still has active tasks in the shared pool`), so the
  driver cannot tell "retryable" from "broken".
- `esm_pseudo_likelihood` still requires an explicit `model_path`.

## Library

`main-v1.1.21`, 7 packages, 1,182 descriptors, 1,074 operators, 108 readers,
79 routes.
