# Operon Studio 5.1.14

5.1.14 fixes result-file download, the remaining gap in the 5.1.13 result API.

## Fix

`Application.artifacts.result()` calls `JobService.result_file()`, but 5.1.13 only
defined `JobService.result_path()`. Local jobs therefore returned HTTP 500 for
`GET /api/v1/jobs/{key}/results/file` and MCP `operon_download_result`, while
listing (`operon_result_files`) worked.

`JobService.result_file(key, relative)` is now an alias for the same containment
and existence checks in `result_path`. No path rule changed.

## Compatibility

Bundle format 1, operator protocol 3 / revision 3.7, built-in library
main-v0.1.1, 79 routes. No operator or graph contract changed.
