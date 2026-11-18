# Operator library main-v1.0.0

Library 1.0.0 is a breaking model release. It requires Operon Studio 5.6.0 or
newer.

## Environment ownership

Every operator belongs to exactly one environment. `operon/environment_assignments.json`
maps operator id to environment name and remains the single source of truth;
`operon/registry.py` stamps `resources.environment` during a registry build and
rejects an assignment that names an environment `operon/environments.json` does
not define. The release now declares 18 environments:

| environment | operators | kind |
| --- | --- | --- |
| core | 1094 | shared runtime |
| proteinmpnn | 26 | weights and code |
| esm2 | 11 | weights |
| genomics | 10 | command line tools |
| esm3 | 6 | weights |
| openmm81 | 6 | python wheels |
| ligandmpnn | 4 | weights and code |
| antismash | 3 | tools and databases |
| boltz | 3 | weights |
| hmmer | 3 | tools and databases |
| rna | 3 | command line tools |
| antifold | 2 | weights |
| hic | 2 | command line tools |
| colabfold | 1 | tool and databases |
| esmfold | 1 | weights |
| openfold | 1 | weights and code |
| rfdiffusion | 1 | weights and code |
| alphafold2 | 0 | planned, databases only |

Each environment lists `requirements`, `pip_wheels`, `pip_pypi`,
`conda_packages`, `binaries`, `imports` and `resources`. The `resources` list
names the resources the environment needs, and every resource points back
through `envs`.

## Official resource units

Every resource declares the units its upstream project publishes. A unit is a
directory or a file and carries `name`, `path`, `mode`, `kind`, `bytes`, `url`
and optional `files`. Sixteen resources declare 26 units, among them the nine
AlphaFold2 units (`params`, `uniref90`, `uniref30`, `bfd`, `mgnify`, `pdb70`,
`pdb_mmcif`, `pdb_seqres`, `uniprot`) and the three RFdiffusion units (the code
tree plus two checkpoints).

`link` and `unlink` accept a unit name; `check_resource` reports per-unit state
so a partially present resource is visible without hiding its missing parts.

## Migration

- Applications older than 5.6.0 must stay on library `main-v0.1.30`.
- Workflows are unchanged; `resources.environment` is additive metadata.
- Saved canvases keep their frozen parameter values.
