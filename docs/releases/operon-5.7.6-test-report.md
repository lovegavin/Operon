# Operon Studio 5.7.6 - test report

Release date: 2026-11-19. Library: `main-v1.1.4`.

## Scope

5.7.6 closes the environment-preparation defects reported against 5.7.5:
platform gating for environments whose command-line dependencies have no
Windows build, readable conda errors, the long-path pip failure, stale
progress after an interrupted preparation, a queue that could stop advancing
after a failing job, a remembered execution target, and per-package dependency
status on the dependency cards.

## Builds

Artifact hashes are recorded in `SHA256SUMS-5.7.6.txt`, delivered next to the
installer and attached to the GitHub release.

| Artifact | Version |
| --- | --- |
| Payload | 5.7.6 |
| Installer | 5.7.6 |
| Server bundle | 5.7.6 |
| Wheel | 5.7.6 |
| Library | main-v1.1.4 |

## Environment matrix on Windows

Every environment was prepared on a clean 5.7.6 installation (port 5806) and
the terminal state was recorded. "Platform" means the environment needs
command-line tools that bioconda and conda-forge publish only for Linux and
macOS; the application now refuses the preparation immediately instead of
starting a download that cannot succeed.

| Environment | Result | Detail |
| --- | --- | --- |
| core | ready | shared runtime dependencies |
| openmm81 | ready | 145 MB |
| ligandmpnn | ready | 1.2 GB |
| esmfold | ready | 2.27 GB, long-path pip fix |
| rfdiffusion | ready | 2.95 GB |
| proteinmpnn | ready | 2.96 GB, 81.7 s |
| esm2 | ready | 2.96 GB, 270.1 s |
| boltz | ready | 2.22 GB, 142.5 s |
| colabfold | install in progress | `dm-haiku` pin removed; preparation was still running when this report was written |
| openfold | ready | 3.01 GB, 38,525 files, torch 2.3.1 CUDA wheel |
| antifold | ready | 4.80 GB, 196.6 s |
| esm3 | ready | 3.83 GB, 203.4 s |
| alphafold2 | ready | 1.90 GB, 58.8 s |
| antismash | platform | hmmer, prodigal, ncbi-amrfinderplus |
| genomics | platform | samtools, minimap2, quast, foldseek, minced, trnascan-se |
| hic | platform | samtools |
| hmmer | platform | hmmer, infernal |
| rna | platform | viennarna, infernal |

## Environment matrix on Linux

The five environments that Windows cannot build were prepared on a Linux
cluster node (`lihj@licai-srv`, Operon 5.7.5 with the 5.7.6 library manifest
and install engine patched in place), using `operon.environment_install.prepare`
directly against `managed-v1/environments`.

| Environment | Result | Detail |
| --- | --- | --- |
| antismash | ready | 7.04 GB, conda `antismash=7.1.0` (the pip pin was wrong) |
| hmmer | ready | 5.21 GB |
| rna | ready | 5.45 GB, `viennarna` from bioconda |
| hic | install in progress | `cooltools==0.6.1` cannot build without a C toolchain, so the pin is removed and the environment is being rebuilt |
| genomics | install in progress | `flye` needs Python 3.10 or older, so the pin is removed and the environment is being rebuilt |

The Linux runs exposed two defects that the Windows platform gate had hidden:
`antismash` was declared as a pip requirement although antiSMASH has no PyPI
distribution, and the channel list was guessed from package-name fragments so
`viennarna`, `samtools` and the assembly tools were solved against conda-forge
only. Both are fixed in 5.7.6.

## Fixed in this release

| Id | Symptom | Fix |
| --- | --- | --- |
| F-69 | Unsupported environment started a download and failed with raw micromamba output | `platform_supported` gate, `platforms` declarations, readable `platform_note` |
| F-70 | `does not exist` lines were unreadable | `readable_conda_error` lists the missing conda packages |
| F-71 | esmfold failed with `OSError: [Errno 22] Invalid argument` | pip `--prefix` no longer uses the extended path prefix on short paths |
| F-72 | Interrupted preparation stayed `installing` forever | `reap_stale` marks it failed with a readable reason after 180 s |
| F-73 | A failing job could stop the preparation queue | `drain_pending` records the failure and keeps draining |
| F-74 | Execution target silently fell back to local | Target is remembered in `localStorage` |

## Interface parity

The dependency cards report `dependency_total` and `dependency_installed`,
each entry carries `installed`, and unsupported environments expose
`supported` and `platform_note`. The same fields are returned for remote
targets, so the local and remote panels render the same state.

## Automated checks

- `pytest tests/test_environment_install.py tests/test_environment_api_runtime.py tests/test_environment_requirements.py`: 28 passed.
- Frontend: 43 files, 265 tests passed; `tsc -b` clean.

## Known limitations

- Environments marked platform-unsupported can still be prepared manually and
  linked, which is the documented path on Linux servers.
- `operon environment status <name>` resolves a workflow directory instead of
  an environment name.
- Large resources that only publish rsync endpoints cannot be downloaded by
  the application; they are reported as such instead of failing silently.

## Still running at publication

Three preparations were still in progress when this report was written and are
tracked as follow-up work rather than claimed as verified results: `colabfold`
on Windows (after the `dm-haiku` pin fix), and `hic` plus `genomics` on Linux
(after the `cooltools` / `flye` pins were removed). Every other row above is a
recorded terminal state from a clean installation.

## Not tested

- GPU execution of the CUDA environments on a machine with a device.
- Full download of the multi-hundred-gigabyte AlphaFold-2 databases.
