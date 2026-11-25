# Operon Studio 5.8.2 acceptance report

Release `5.8.2` ships with operator library `main-v1.2.1`. This report covers the
three defects fixed in this patch; the full 1074-operator acceptance matrix is
the one recorded in `operon-5.8.0-test-report.md`, whose build already carries
every operator fix up to `87def598d`.

The release commit carries this report; `git status` was clean and the payload
manifest records `source_dirty: false`.

## What broke, and where it was observed

The defects were reported from real structure routes executed through MCP on
`licai-srv` (server build `5.8.0`):

| Job | Input | Symptom |
| --- | --- | --- |
| `exec-b569…f59d` (mmCIF into `structure_extract_chain`) | mmCIF via `PdbReader` | `'NoneType' object is not iterable` |
| `exec-a807…f3a5`, `exec-a9aa…50f3d` (`structure_convert_format` → `structure_extract_chain`) | PDB chain A/B | `no atoms belong to chains B` |

## Fix 1 — PDB text is decoded before it is written

`structure_convert_format` took the Form columns as they were stored. A reader
that label-encodes chain, residue name or atom name stores integers, so the
written PDB had `'0'`/`'1'` in the chain column. The operator now inverts every
text column through `form.info['encoders'][field_dim]` (aliases included) and
decodes `residue_number` when that column carries an encoder.

## Fix 2 — the chain guard and the chain decode agree

`structure_extract_chain` accepted `chain`, `label_asym_id` and `auth_asym_id`
in its guard but decoded only `chain`, so a form read from mmCIF (which carries
`label_asym_id`) returned `None` and the operator iterated over it. The operator
now resolves the chain column through the same alias list, decodes the other
structural columns the same way, and a wrong chain request reports the chains
the input actually carries:

```
structure_extract_chain: no atoms belong to chains B; the input carries A
```

## Fix 3 — a declared path falls back to the launching host

38 operator parameters that name a structure or FASTA file now declare
`x-operon-path` (ProteinMPNN, LigandMPNN, RFdiffusion, AntiFold, AlphaFold-2,
ESM3 inverse folding, and the structure helpers). The planner previously checked
those paths only on the target host; `resolve_reference()` now probes the target
first and, when the file is missing there but present locally, marks the
reference local so the existing upload step ships it. A pinned
`file_locations` entry still wins.

## Tests

| Suite | Result |
| --- | --- |
| `tests/test_structure_label_decoding.py` | 7 passed |
| `tests/test_reference_fallback.py` | 6 passed |
| `tests/test_execution_plan.py` | 40 passed |
| `tests/test_remote_cleanup.py`, `tests/test_remote_upgrade_retire.py` | 8 passed |
| `python3 -m operon registry build --scope routes` | 1074 operators / 109 readers / 79 routes / 0 errors |

The decode tests build Forms by hand with a `LabelEncoder`, run both operators,
and assert the written PDB carries `A`/`A`/`B` in the chain column, that a form
with only `label_asym_id` extracts chain B, and that a missing chain column
raises the readable `StepError`. The reader is stubbed because the development
tree's reader registry records mtime-based implementation hashes that a source
checkout cannot satisfy; the real reader path is exercised on the server.

## Not covered here

The three defects were reproduced on the `5.8.0` server build. Re-running the two
structure routes against a server carrying `5.8.2` is the remaining check and is
scheduled with the next deployment; this release was published from a clean
build without deploying the remote, as requested.
