# Operator library main-v1.0.1

Library 1.0.1 requires Operon Studio 5.6.1 or newer.

## One official unit per resource

Every resource now declares exactly one official unit, named after the folder or
file the upstream project publishes. Sixteen resources therefore declare sixteen
units:

| resource | unit |
| --- | --- |
| proteinmpnn | `ProteinMPNN` |
| ligandmpnn | `LigandMPNN` |
| rfdiffusion | `RFdiffusion` |
| esm2 | `esm2_t6_8M_UR50D.pt` |
| esm_if1 | `esm_if1_gvp4_t16_142M_UR50.pt` |
| esmfold | `esmfold_3B_v1.pt` |
| colabfold | `colabfold` |
| alphafold2 | `afdb` |
| prodigal | `prodigal` |
| pfam | `Pfam-A.hmm` |
| rfam | `Rfam.cm` |
| amrfinder | `amrfinder` |
| antismash | `antismash` |
| boltz | `boltz` |
| antifold | `antifold` |
| openfold | `openfold` |

The AlphaFold2 databases that used to be nine linkable units are all published
inside a single `afdb` directory upstream, so the resource links as that one
folder. Completeness is still reported file by file: `check_resource` returns
the nine declared files with their presence state, and the application shows
them in the resource detail view.

## Environment ownership

`operon/environment_assignments.json` still maps all 1,177 descriptors to the 18
environments of library 1.0.0; the registry stamps `resources.environment` on
every descriptor and rejects an unknown environment name. Each environment keeps
its dependency and resource lists.

## Migration

- Applications older than 5.6.1 must stay on library `main-v1.0.0`.
- Workflows are unchanged; the unit layout only affects how a resource is
  downloaded or linked.
- A resource that was linked as one of the previous AlphaFold2 sub-units should
  be linked again as `afdb`.
