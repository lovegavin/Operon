# Operon Studio 5.7.1 test report

## Builds

| Artifact | Size | SHA-256 |
| --- | --- | --- |
| `Operon-Studio-v5.7.1-Windows-x64.zip` | 357,453,933 | `05fc5dc6b131c677e451997dce1d467ce15f31b464c4790b13bda07eac9e9e72` |
| `Operon_Setup-5.7.1.exe` | 429,231,288 | `88e71ada3670ae2dc9529593d3e7200c803e9f03c10e1654ccb18f9fb216b303` |
| `Operon-5.7.1-Server.zip` | 9,815,744 | `606404cd6473965ac7f5c658a46bace036ccfb2080d0916fb373b265e189d5e4` |
| `operon_studio-5.7.1-py3-none-any.whl` | 995,638 | `64f28d0165085e56fea9456dc925d48a63989bf86232825aade103a89525cb04` |
| `operon-library-main-v1.1.1.operon-library.zip` | 6,989,564 | `8fc46c1da2ac4d330445c660ceb2f550ff9cb59d50a8d7c3cdabd4bf20b1acdc` |
| `operon-routes-main-v1.1.1.zip` | 201,221 | `06bb0a9bce5feac88b01038a30f85bf878c2484c916a82e605804f5291aca34b` |

## Clean installation

Installed with `Operon_Setup-5.7.1.exe --quiet` into a fresh directory; the
service reported ready 19 s after launch and `/api/version` returned
`5.7.1 (40e70ded)`. The installed library is `main-v1.1.1` with 18
environments, 1,181 descriptors (1,073 operators, 108 readers), 16 resources
and 16 units.

## Behaviour checks

- `POST /api/environments/prepare {"names": ["openmm81"]}` queued exactly one
  environment; the response `prepared` list contained `openmm81` only.
- `POST /api/environments/prepare {"names": ["openmm81"], "bogus": 1}` returned
  HTTP 422 and queued nothing.
- `GET /api/environments` reports `alphafold2` with `planned: false`,
  `operator_count: 4` and `dependencies: [{"kind": "requirements", "name": "numpy"}]`.
- `POST /api/v1/large-resources/alphafold2/download {"unit": "afdb"}` started a
  per-file download and created `params/params_model_1_ptm.npz.part`, i.e. only
  the declared member of the parameters tarball is transferred; the previous
  behaviour stored the GitHub project page as a 409,718-byte file named `afdb`.
- The resource card for a unit that only documents a project page now raises
  `resource '…' unit … only documents a project page …` instead of writing HTML.
- Progress labels use the dark text colour on the light track, and the bar caps
  at 99% until the environment actually becomes ready (then it is replaced by
  the ready badge).

## MCP surface

`python -I -m operon mcp` exposes 75 tools. The resource family now accepts
`unit` and `profile_id`, and three library-synchronisation tools
(`operon_remote_library_plan`, `operon_remote_library_sync`,
`operon_remote_library_status`) were added.

## Regression suites

- `tests/test_remote_library.py` + `tests/test_alphafold2_operators.py`:
  24 passed.
- `tests/test_environment_api_runtime.py` + `tests/test_resource_download_units.py`
  + `tests/test_resource_api.py`: 27 passed.
- `tests/test_environment_install.py`, `tests/test_environment_api.py`,
  `tests/test_environment_api_runtime.py`: 16 passed (pre-patch baseline).
- Frontend: 43 files / 265 tests passed; `tsc -b` clean.

## Known limitations

- BAM inputs still need `pysam`, which has no Windows wheel; those operators
  report the missing dependency instead of fake success.
- `operon environment status <name>` still resolves through the working
  directory rather than the installed library.
- `/api/browse` and single-dependency install/cancel have no MCP tool yet.
- The three largest AlphaFold database sources (UniRef30, MGnify, BFD) can be
  linked but their tarballs are not yet declared as per-file downloads.