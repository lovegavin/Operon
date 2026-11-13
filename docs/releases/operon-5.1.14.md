# Operon Studio 5.1.14

5.1.14 fixes result-file download, the remaining gap in the 5.1.13 result API.

## Fix

`Application.artifacts.result()` calls `JobService.result_file()`, but 5.1.13 only
defined `JobService.result_path()`. Local jobs therefore returned HTTP 500 for
`GET /api/v1/jobs/{key}/results/file` and MCP `operon_download_result`, while
listing (`operon_result_files`) worked.

`JobService.result_file(key, relative)` is now an alias for the same containment
and existence checks in `result_path`. No path rule changed.

## Verification

- Installed silently as `5.1.14-10b2d136e0a9`; `operon.cmd --version` reports `Operon 5.1.14`.
- Built-in library `main-v0.1.1` (1174 descriptors) and the four environment declarations load from the installed tree.
- Focused tests: `tests/test_result_downloads_5113.py` 5 passed, including the `result_file` alias test.

## Artifacts

| Asset | Size | SHA-256 |
| --- | ---: | --- |
| `Operon_Setup.exe` | 426,748,388 | `090135dcc88afe9e2bee3615ccb2de6413db3a789d56c1efd96913055e31bee6` |
| `Operon-5.1.14-Server.zip` | 9,166,996 | `8956e5c27418b0c83c486402384977fb4b0beb5128da28a7a00b83ff4c2fa9ed` |
| `operon_studio-5.1.14-py3-none-any.whl` | 674,968 | `0aa742b5a829378bfffe179968c4a00f4ee6eba68984789ef73091a292b3e8a8` |

## Compatibility

Bundle format 1, operator protocol 3 / revision 3.7, built-in library
main-v0.1.1, 79 routes. No operator or graph contract changed.
