# Operator library main 1.0.2

Library `main-v1.0.2` is the first library in which every operator belongs to
exactly one environment and every resource names the official unit that
upstream publishes.

## Contents

- 7 packages, 1,177 descriptors, 1,069 operators, 108 readers.
- 18 environments; the assignment of all 1,177 descriptors is stored in
  `operon/environment_assignments.json` and stamped into each descriptor by the
  packager.
- 16 resources with 16 official units:

| Resource | Official unit |
| --- | --- |
| proteinmpnn | ProteinMPNN |
| ligandmpnn | LigandMPNN |
| esm2 | esm2_t6_8M_UR50D.pt |
| esm_if1 | esm_if1_gvp4_t16_142M_UR50.pt |
| esmfold | esmfold_3B_v1.pt |
| colabfold | colabfold |
| alphafold2 | afdb |
| rfdiffusion | RFdiffusion |
| prodigal | prodigal |
| pfam | Pfam-A.hmm |
| boltz | boltz |
| rfam | Rfam.cm |
| amrfinder | amrfinder |
| antismash | antismash |
| openfold | openfold |
| antifold | antifold |

## Changes since 1.0.1

- The packager stamps `resources.environment` into packaged descriptors and
  recomputes the declaration hash; 1.0.1 shipped 1,157 descriptors without an
  environment.
- Environment titles are short Chinese labels.
- `alphafold2` keeps one unit (`afdb`) instead of nine sub-units.

## Compatibility

Requires Operon Studio 5.6.2 or newer.
