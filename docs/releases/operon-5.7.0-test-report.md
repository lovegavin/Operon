# Operon Studio 5.7.0 test report

Environment-first runtime with operator-library synchronisation, AlphaFold2
operators and a FileArtifact-aware environment bridge.

## Builds

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| Operon-Studio-v5.7.0-Windows-x64.zip | 357,441,289 | 5a2e4388a763bbe8be6ae645d8ba894e0f4a27bc9c73adc7fc327d3cf88b0005 |
| Operon_Setup-5.7.0.exe | 429,218,641 | a0a32c1e0cabfb34de305c2a06c7fcbd95ca3ac58e4bbd757a1a3ec716a01d23 |
| Operon-5.7.0-Server.zip | 9,809,754 | 6f76c7d7e260fabb82e8e7cf1f1051df9a510e2ed93f22f123581ceb5a3f6434 |
| operon_studio-5.7.0-py3-none-any.whl | 994,659 | 400ec988ed1f53a70ae1a8b25374138a8287155e14ad3578802c6e665d0a94ac |
| operon-library-main-v1.1.0.operon-library.zip | 6,989,691 | 4a77e465942e9a62f45a9f9c0c05bbb610179b71fdc477aacbd19a0a1514e2dc |
| operon-routes-main-v1.1.0.zip | 201,408 | 4c2678abd405f3c0a8ef44a1ef9208843b2e8a3da8cba30ccea7e6f4baaaa3e8 |

## Clean installation

| Check | Result |
|---|---|
| Installer duration | 19.4 s (5.7.0-e630e57a8e1c), 21.4 s (5.7.0-47e8dc3470f0) |
| /api/version | 5.7.0 build 47e8dc3470f0 |
| Library | main-v1.1.0, 7 packages, 1,181 descriptors, 1,073 operators, 108 readers |
| Environments | 18 |
| Resources | 16 resources, 16 components |
| alphafold2 card | planned false, operator count 4, requirements empty (shell environment) |

## AlphaFold2 operators

Four operators were added to the library (predict, batch_predict, msa_search,
rank_models). They invoke an external `run_alphafold.py` checkout through the
`runner`/`python_executable` parameters, so the environment itself only needs a
Python shell.

`tests/test_alphafold2_operators.py` covers the operator contracts with a stub
runner: 10 passed in 0.60 s. End-to-end submission against a real AlphaFold-2
checkout was not exercised in this build; the environment was still being
created when the build was packaged.

## Environment bridge

F-55 fixed the cross-process transport of file artifacts: `_write_form` and the
environment worker now serialise and rebuild `FileArtifact` values (format,
files, info, fingerprints) instead of assuming numpy payloads. `genotype_grm`
with a VcfFileReader source completed after the fix, which was previously
impossible (`'FileArtifact' object has no attribute 'data'`).

## Operator library synchronisation

`GET /api/remote/{key}/library/plan` reports the packages that are missing on a
target and the remote-only packages that a force sync would remove.
`POST /api/remote/{key}/library/sync` installs the missing packages, removes the
extra ones and refreshes the remote registry. Remote agents advertise
`library_remove_v1`; older agents report the removal as unsupported instead of
failing silently.

Stub-level tests: `tests/test_remote_library_sync.py` and
`tests/test_remote_library.py`, 16 passed in 33.3 s.

## UI verification

Headless browser against the clean 5.7.0 installation:

* 18 environment cards, no duplicated card text (`duplicateText = 0`).
* AlphaFold2 card renders the environment name, the descriptive title, the
  installation percentage and real byte progress, and no `reserved` badge.
* Detail view keeps the two entry cards (dependencies, resources), the unit
  card and the sticky footer.
* Remote target selection still lists only machines that are connected.

## Regression suite

Sub-agent run, no source edits:

| Group | Result |
|---|---|
| Environment | 35 passed |
| Resource and remote | 82 passed, 1 skipped (directory junctions are Windows-only) |
| Operator docs | 13 passed |
| Control API | 1 passed |
| Total | 132 collected, 131 passed, 1 skipped, 0 failed |

`tests/test_registry_maintenance.py` and `tests/test_manifest_registry.py`
reported six failures in the same run because the new AlphaFold2 operators were
still untracked in `builtin_packages.json` at that moment; the registry was
rebuilt afterwards.

## Operator coverage

The coverage harness re-submitted 1,069 operators against the installed build.
At the time of packaging 115 operators had produced a complete run, and the
remaining ones were attributed to concrete gaps:

| Bucket | Count | Meaning |
|---|---:|---|
| other | 234 | domain-specific errors not yet classified |
| column | 81 | the operator requires specific column names |
| insufficient | 40 | sample data too small for the statistic |
| file | 33 | requires a file-artifact representation |
| envnotready | 27 | isolated environment not installed |
| empty | 29 | no error reported, job produced no run |
| connection | 9 | service restarted during the run |
| timeout | 2 | exceeded the client wait |
| token | 499 | historical rows submitted with a stale session token |

The 499 token rows and the 33 file rows most likely recover on a re-run with the
current build; that re-run is still in progress and is not part of this build's
verdict.

## Known limitations

* `operon environment status <name>` still resolves the name against the current
  working directory rather than the installed library.
* AlphaFold2 operators need an external checkout; the packaged environment only
  provides the interpreter shell.
* `pysam` has no Windows wheel on this machine, so BAM-only operators cannot run
  in the packaged environment.
