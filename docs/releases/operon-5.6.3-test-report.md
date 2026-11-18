# Operon Studio 5.6.3 test report

## Scope

Card-based runtime navigation (environment -> dependencies/resources -> official
units), percentage progress, footer back control, per-unit download URL and
missing-file report, and the remote/local manifest warning.

## Builds

| Artifact | Bytes | SHA-256 |
| --- | --- | --- |
| Operon-Studio-v5.6.3-Windows-x64.zip | 357,354,203 | 9c83f300cda4b702b657120e73eae7a340095df7983e3416cda8d25276d509a2 |
| Operon_Setup-5.6.3.exe | 429,131,563 | c233c105432f4b107b442246462d79fe1a0dbc54ea271a78d32767a630320aab |
| operon_studio-5.6.3-py3-none-any.whl | 992,674 | d19e5c01cf3b67ac1a171a83f383bcb12e5043ed7f1ebcecfd8d8ba0f3cc1f27 |
| Operon-5.6.3-Server.zip | 4,757,303 | 9b022a958c916d8884605d2573ccfbdc932cc816135fed189462203088b2017d |
| operon-library-main-v1.0.2.operon-library.zip | 6,949,024 | 3f2c672e13094ee66fede0256bc4707a2d3985ab5eedd162d70d776a02e52b1f |

## Clean install

Installed with `--quiet --no-register --result` into an empty directory; the
bundled server answered `/api/version` with `5.6.3 (8811baa4)`.

| Check | Result |
| --- | --- |
| `/api/version` | 5.6.3 |
| environments | 18 |
| operators assigned | 1,177 |
| resources | 16 |
| official units | 16 |
| `/api/libraries` | main-v1.0.2 |
| `/api/browse` | drive roots and directory listing returned |

## Interface parity

`operon environment list`, `operon environment status`, `operon resources list`,
`POST /api/environments/{name}/dependencies/download` and the MCP counterparts
share the same service; HTTP and CLI were exercised on the installed build.

## UI verification

Headless browser against the installed build:

- 18 environment cards, Chinese short titles, execution-location selector present
- summary strip shows `18 environments / 18 not installed`
- environment detail: two entry cards, dependency card reports the dependency
  count, unit card shows the official name, the download URL and the action row
- percentage progress fill element is used instead of the old sweep animation
- back control rendered in the dialog footer

## Automation

| Suite | Result |
| --- | --- |
| Frontend unit tests | 43 files, 265 tests passed |
| Resource/environment suites | 43 passed, 1 skipped |
| Resource link suite | 27 passed, 1 skipped |

## Known limitations

- `operon environment status <name>` still expects a workflow directory.
- Free-space preflight compares the estimate against the free bytes at the
  destination; it does not account for shared inodes.
- `alphafold2` declares no operator yet; the environment exists for a future
  local AlphaFold-2 runner.

## Not tested

- Long-running downloads against the public mirrors were not repeated in this
  cycle; the percentage rendering was verified with API-driven progress states.
