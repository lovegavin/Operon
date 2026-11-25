# Operon Studio 5.8.2

Released 2026-11-25. Library: main-v1.2.1.

5.8.2 fixes three defects that a real structure pipeline exposed, and makes a
declared file parameter usable when the file only exists on the machine that
launched the job.

## Fixed

- **A structure written back to PDB keeps its chain letters.** The
  `structure_convert_format` operator took columns straight from the Form, so a
  label-encoded integer (0–6) was written where a chain id belongs and the file
  read `0`/`1` instead of `A`/`B`. Every text column (chain, residue name, atom
  name, element, altloc, insertion code) is now inverted through
  `form.info['encoders']` before it reaches the file, and the residue number is
  decoded too when it carries an encoder.
- **`structure_extract_chain` reads the chain column through its aliases.** The
  guard accepted `chain`, `label_asym_id` and `auth_asym_id`, but the decode
  call only asked for `chain`; a form read from mmCIF therefore raised
  `'NoneType' object is not iterable`. The operator now decodes through all
  three aliases, decodes the other structural columns the same way, and reports
  which chains the input carries when the requested one is absent.
- **A declared path parameter falls back to the launching host.** The planner
  only checked a `x-operon-path` parameter on the target host, so a PDB or FASTA
  that existed locally but not on the server failed with "input file
  unavailable". `src/web/execution_plan.py::resolve_reference` now probes the
  target first and, when the file is missing there but present locally, records
  the reference as local so the normal upload path moves it to the server. A
  pinned `file_locations` entry still wins.

## Library

Library 1.2.1 declares `x-operon-path` on the structure and FASTA parameters of
38 operators (ProteinMPNN, LigandMPNN, RFdiffusion, AntiFold, AlphaFold-2,
ESM3 inverse folding and the structure helpers) and ships the two structure
fixes above. Operators, readers and routes stay at 1074 / 109 / 79.
