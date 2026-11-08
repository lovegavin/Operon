# Skip inventory for the 6.0.0 test run

Source: full `python -m pytest -q -rs` run in `/home/gavin/bp-numpy21`
(NumPy 2.1.3) on 2026-11-08, 223 skipped tests, 68 distinct skip reasons.
Reasons are grouped by the dependency or fixture that is absent; no test was
skipped because of a library defect.

| Group | Count | Representative reason |
| --- | --- | --- |
| R / Bioconductor tooling absent | 128 | `Rscript is not available` (DESeq2, edgeR, limma, metagenomeSeq, ...) |
| Hi-C tooling absent | 14 | `could not import 'hictkpy'`, `Set OPERON_HIC_REAL=1 ...` |
| Protein-model checkpoints absent | 18 | ESM-IF checkpoint, `fair-esm` shadowed by ESM-3, `OPERON_ESM_CHECKPOINT` unset |
| Real SOP fixtures not shipped | 14 | `real SOP fixture is not present: tasks/*/input/...` |
| Windows-only paths | 4 | `Windows native import paths`, `Windows package resource paths` |
| Assembly / design tools absent | 8 | OPERON_REAL_ASSEMBLY, ProteinMPNN, LigandMPNN checkpoints |
| Optional Python packages absent | 9 | `allel`, `linearmodels`, `mudata`, `mrcfile` |
| Platform ABI incompatibility | 1 | `torch_scatter` built for a different ABI |
| Miscellaneous environment gates | 27 | viewer lifetime on Windows, server setup without a usable Python |

The R-dependent group dominates because the verification host has no
R/Bioconductor installation; the corresponding operators carry their numeric
checks in the library test-suite through pure-Python oracles. Protein-model
and assembly entries require multi-GB checkpoints that are intentionally not
downloaded on this host. Real SOP fixtures are public datasets referenced by
URL and are fetched only in the dedicated SOP environments.
