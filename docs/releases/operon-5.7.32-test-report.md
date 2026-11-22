# Operon Studio 5.7.32 acceptance report

Every fix below was found by running the operator catalogue against real data
through MCP, not by reading code. The sweep has submitted **1,147 jobs** to the
Linux server at the time of this build: 475 reached `complete`, 671 `failed`,
one still running. 589 of the 1,074 operators have been attempted, 294 of them
completed at least once.

## Defects closed in this build

| Symptom | Real cause | Fix |
| --- | --- | --- |
| `FASTA reader: unsupported label rule for 'position': 'builtin'` on assembly, codon, antibody and AMR operators (20+ operators) | The reader documented `builtin` and both the reader default and the form editor used it, but `read()` only accepted `None`, `auto` and a mapping | `fasta_reader.read()` accepts `builtin`, which means the residue index, exactly like `auto` |
| `StepError: No module named 'pydantic'` inside isolated workers (18 operators across `core`, `hmmer`, `esm2`, `boltz`, `proteinmpnn`, `genomics`) | `operon/env_worker.py` imports `operon.plugins` to rebuild the reader table; that chain reaches `operon_sdk.protocol`, which is pydantic. Environments that never listed pydantic could not start a step | `pydantic>=2.7` is now a requirement of all 19 environments |
| `cannot load ESM checkpoint ...: No such file or directory: ...-contact-regression.pt` | fair-esm's `load_model_and_alphabet_local` loads the regression head for every `esm2_*` checkpoint; the resource only shipped the model weights | The `esm2` resource ships `esm2_t6_8M_UR50D-contact-regression.pt` (1,511 B, official `fair-esm/regression` URL) |
| Jobs stuck in `waiting_connection` for 36 minutes while `operon_remote_status` said `connected: true` | The call path never reconnects and the wait has no deadline | Reconnect once (and once after a stale channel), and fail after `OPERON_DISCONNECT_SECONDS` (900 s) with an actionable message |

## Evidence

- `iris.csv` → `CsvReader` → `pca` completed in **16.8 s** (`exec-3a7273794fb84abab1d28eb13f99c1cc`) once the row label rule was written as
  `labels: {"sample": {"feature": 0}}`.
- `esm2_t6_8M_UR50D.pt` now loads as an `ESM2` model in the `esm2` environment
  with the regression head co-located.
- FASTA read-back is verified on the server: the same VHH record that raised the
  label-rule error now reaches the operators that consume it.
- Environment inventory after the upgrade: 19 environments, all `ready` except
  `openmm81` pending re-installation because its requirement list changed.

## Known gaps at this build

- `vina==1.2.5` remains the only optional binding without a cp311 wheel; the
  conda-forge build exists but the mirror occasionally answers 403.
- Shared-pool version switching (`Another Operon version still has active
  tasks`) is still reported as an operator failure; it should be retryable.
- `esm_pseudo_likelihood` still requires an explicit `model_path`.
