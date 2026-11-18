# Operon Studio 5.5.3 test report

Verification of the 5.5.3 release on a clean Windows installation: installer,
headless server, HTTP API, MCP surface and the desktop frontend rendered in a
headless browser.

## Environment

| Item | Value |
| --- | --- |
| Application | 5.5.3 |
| Library | main-v0.1.30 (7 packages, 1,177 descriptors, 1,069 operators, 108 readers) |
| Installer | `Operon_Setup-5.5.3.exe`, per-user install, no registration |
| Host | Windows 10.0.19045, Python 3.11.18 runtime shipped with the payload |
| Server | `python -m operon` variant used by the desktop entry point, port 5779 |

## Install

| Check | Result |
| --- | --- |
| Installer exit code | 0 |
| Duration | about 20 s |
| Version directory | `5.5.3-589cc86e1e40` |
| `/api/version` | `{"version":"5.5.3","build":"589cc86e1e40","display":"5.5.3 (589cc86e)"}` |
| `/api/libraries` | `main-v0.1.30`, 7 packages, 1,177 descriptors |

## Library and resource surface

| Check | Result |
| --- | --- |
| `/api/environments` | 7 environments, 16 resources, 18 used-by pairs |
| `/api/v1/large-resources` | 16 resources |
| `official_root` present | 16 of 16 |
| `link_unit` split | 10 tree, 6 items |
| State distribution | linked 1, downloaded 2, partial 1, missing 12 |
| AlphaFold2 | `official_root: "afdb"`, 9 expected files, 9 file entries, none present, state `missing` |
| Remote profile (unknown) | `GET`/`POST`/`DELETE` return `404` with `No such server connection.` |

Junction handling was verified end to end: `mklink /J` on a prepared directory
produced `state: "linked"`, `root_linked: true`, `units[0].receipt: false`;
`DELETE /api/v1/large-resources/antifold/link?unit=tree` answered
`{"status":"unlinked","mode":"junction"}` and the resource returned to
`state: "missing"`.

## Desktop frontend

Rendered at 1440x900 through the Chrome DevTools Protocol against the installed
build.

| Check | Result |
| --- | --- |
| Runtime panel | 16 resource cards, grouped by environment, each with state chip |
| Official name on card | `afdb` for AlphaFold2, `ProteinMPNN`, `RFdiffusion`, `Pfam-A.hmm`, `Rfam.cm` for the other special cases |
| Detail dialog | title AlphaFold2 parameters - required files, note Official directory or file: afdb. After linking, Operon checks the files inside it., all nine entries marked missing |
| Dialog actions | `Relink this directory`, `Download`, `Unlink`, `Close` |
| Console errors | none |

Screenshots: `ui553-runtime.png` (card list), `ui553-detail.png` (missing
files), `ui553-link.png` (link dialog).

## Automated tests

| Suite | Result |
| --- | --- |
| `tests/test_environment_install.py test_environment_api_runtime.py test_environment_queue.py test_environment_estimates.py` | 27 passed |
| `tests/test_resource_link.py test_resource_fetch.py test_resource_link_control_api.py test_resource_api.py test_remote_resources.py` | 59 passed, 1 skipped |
| Frontend `npm test` | 43 files, 265 tests passed |
| Frontend `tsc -b` | no diagnostics |

The full backend suite was last run against the 5.5.1 tree: 97 failed,
4,723 passed, 282 skipped, 10 errors (3,485 s). The failures are pre-existing
and environmental (optional analysis dependencies, SSH host requirements, git
history checks, repository hygiene); the resource and environment modules under
change in this release were green.

## Not tested

- Windows 11 and macOS hosts.
- Servers without a GPU for the structure-model environments.
- Linking across machines (by design the link is local to the executing host).
