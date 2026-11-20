# Operon Studio 5.7.15 test report

## Scope

Defect-only release for the operator execution bridge and the `core`
environment definition.

## Defects

| ID | Symptom | Fix |
| --- | --- | --- |
| F-107 | `('Form', 'orphan encoder column.chain')` shown to users | `OperonError.__str__` joins its arguments and the form validation message names the column and dimension |
| F-108 | `No module named 'pandas'` for 147 of 243 measured operator failures | `core` requirements now include the scientific stack |
| F-109 | `quast/antismash/amrfinder: not on PATH` although the tool is installed | the declared environment's `bin` is prepended to `PATH` for the step |
| F-110 | `'Context' object has no attribute 'artifact_path'` | the bridged `Context` exposes `out_dir`, `memory` and `artifact_path` |

## Builds

| Artifact | Bytes | SHA256 |
| --- | --- | --- |
| Operon-Studio-v5.7.15-Windows-x64.zip | pending | pending |
| Operon_Setup-5.7.15.exe | pending | pending |
| Operon-5.7.15-Server.zip | pending | pending |
| operon_studio-5.7.15-py3-none-any.whl | pending | pending |
| operon_builtin_library-1.1.9-py3-none-any.whl | pending | pending |
| operon-library-main-v1.1.9.operon-library.zip | pending | pending |
| operon-routes-main-v1.1.9.zip | pending | pending |

## Installer actions (action audit)

| Action | Endpoint | Result |
| --- | --- | --- |
| Prepare environment | `POST /api/environments/prepare` | 200, status becomes `installing` |
| Cancel preparation | `POST /api/environments/{name}/cancel` | 200, environment returns to `missing` |
| Retry environment | `POST /api/environments/{name}/retry` | 200 response payload |
| Install dependency before ready | `POST /api/v1/environments/{name}/dependencies/download` | 409 with readable message |
| Download resource unit | `POST /api/resources/{name}/download` | 200, operation `running` |
| Read environment log | `GET /api/environments/{name}/log` | 200 with log text |
| Remote dependency counts | `environment_snapshot` | 10/10, 7/7, 6/7, 6/8 for four sample environments |

## Automated checks

- `pytest tests/test_env_worker_context.py tests/test_environments.py -q` -> 8 passed.
- `pytest tests/test_form_validation_errors.py -q` -> 3 passed.
- `pytest tests/test_operator_input_validation.py -q` -> 15 passed.

## Operator coverage

Coverage numbers for this build are produced on Linux, where all eighteen
environments are installable. The previous measurement before the `core`
dependency fix was 61 completed of 304 attempted (243 failures, of which 169 were
`environment_not_ready` and 147 cited `pandas`). The follow-up sweep runs against
the same library and reports its numbers in
`docs/verification/linux-coverage-5.7.15.md`.

## Known limitations

- The Windows host cannot install `antismash`, `genomics`, `hic`, `hmmer` and
  `rna`; those environments stay `missing` with a platform note.
- Operators that need external reference data (GO OBO/GAF, ESM weights) require
  the user to provide an absolute path.
- `operon environment status <name>` still resolves the name as a workflow
  directory.

## Not tested

- Long-running downloads of multi-hundred-gigabyte databases were not re-run.
