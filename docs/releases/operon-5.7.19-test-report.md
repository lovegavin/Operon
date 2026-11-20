# Operon Studio 5.7.19 test report

## Builds

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `Operon-Studio-v5.7.19-Windows-x64.zip` | 357,765,125 | `c419971afd7c57e61c80a253a0537526680b2f120f4f04b1df85ce195a57fa10` |
| `Operon_Setup-5.7.19.exe` | 429,542,490 | `83b04e39884bedd1d065c7681656a5270a003fbe519963150abc43a1172e40e2` |
| `Operon-5.7.19-Server.zip` | 9,937,647 | `db996c7172c59e17de1bf772aa66bd299cb15d99547cc73236c084be155fae97` |
| `operon_studio-5.7.19-py3-none-any.whl` | 1,018,535 | `0a5b7d793a707875766e6988255eaa7442af30d9ec94eace3c559e99f027e2f1` |

## Clean install

| Step | Result |
| --- | --- |
| Installer | exit 0, 18.4 s, version directory `5.7.19-d932b816b851` |
| Service ready | 60.9 s, `/api/version` = `5.7.19 (d932b816)` |
| Acceptance (`check93.py`) | 24 checks, 0 failures |
| Library | `main-v1.1.12`, 1,074 operators, 1,182 descriptors, 7 packages, 108 readers |
| Environments | 18 listed, five states present, no "prepare failed" chip |
| Conda channel check | `POST /api/v1/environments/core/dependencies/download` returned 200 with a job (no 500) |

## Automated checks

- `pytest tests/test_mcp_parity.py tests/test_environment_install.py tests/test_mcp_server.py -q`
  → 66 passed.
- Frontend `npm test -- --run` and `npm run build` are run in the Windows mirror
  before packaging.

## Installer behaviour covered by this release

- Conda environment creation no longer trips the 300 second silence guard; the
  grace period is 1800 seconds and package cache growth counts as activity.
- `OPERON_CONDA_CHANNELS` is honoured by the create, install and repair paths.
- A legacy artifact entry no longer fails the whole artifact index.

## Not tested

- A full Alphafold2 environment build on a machine whose conda channel is slow;
  the fix is covered by unit tests plus a manual probe of the mirror.
