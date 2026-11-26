# Operon 5.11.1 test report

## Automated

- `tests/test_structure_label_decoding.py` (convert/extract with `.` residue
  numbers), `tests/test_extension113.py` (protein FASTA keeps `:`),
  `tests/test_colabfold_sequence.py` (raw sequence preference):
  18 passed, 1 skipped.
- `tests/test_nodes.py` + `tests/test_execution_plan.py`: 74 passed
  (compute-node scoring and request validation from 5.11.0).
- Frontend `npx tsc -b && npx vitest run`: 289 passed (44 files).

## Manual, against licai-srv

- `alphafold2` environment: `import simtk.openmm.app.internal.pdbstructure`
  succeeds after a declarative repair, and the `params` unit now lists fifteen
  files, including the five multimer weights.
- Structure conversion and chain extraction are to be re-run on the user's
  3DI3 mmCIF; ColabFold is to be re-run with the `IL-7:IL-7RA` FASTA.
- RFdiffusion and Boltz are to be re-run after the 5.11.1 deployment.

## Known limits

- A full AF2 multimer prediction spends hours in MSA search on CPU; the
  parameter fix is verified by resolution/import, not by a full prediction.
- The compute-node placement feature from 5.11.0 is unchanged here.
