# Operon Studio 5.4.6

Released 2026-11-17. Baseline: 5.4.5.

5.4.6 fixes the operator catalog going stale in the desktop window and adds
route-library collections that can be removed as a unit.

## Fixed

| Symptom | Cause | Change |
| --- | --- | --- |
| Operator sidebar stopped at an old count (for example 840 while the server reported 1069) and never recovered until the window was reloaded. | The 5 s catalog poll used a single-flight `pending` flag and fetched without a timeout. One request that never settled left `pending` true forever, so no later poll ran and `catalogUpdates` never received the new catalog. | `api.request()` accepts `timeoutMs` and passes `AbortSignal.timeout(...)`; the poll gives catalog, routes and library state 20 s. A cycle in flight longer than 30 s is abandoned instead of blocking the next one, and revisiting the window reloads the full catalog with `catalogUpdates.force()`. |
| Route libraries could be imported but not removed: the only way out was deleting routes one by one. | `install_routes_collection` registered the routes and returned their keys without recording which library they came from. | The importer writes `routes/collections/<slug>.json` with the source name, import time and the routes it created. `GET /api/route-collections` lists them and `DELETE /api/route-collections/{slug}` unregisters every route in the collection and removes its saved graph, parameters and execution records. The import panel shows the imported collections with a remove action. |
| Nine message keys were translated in English only, so Chinese windows fell back to the English string. | The Chinese projection was missing keys added by later panels. | `zh-CN.json` now covers `取消准备`, `导出独立运行包`, `正在提交`, `正在自动准备`, `用原标识确认提交结果`, `用原标识确认运行`, `路线运行与导出记录`, `输出目录（留空自动创建）` and `运行路线`. |

The base-library marker (`library/base-library.json`) still prevents the built-in
library from reappearing after every branch was deleted on purpose. A window that
loses its catalog no longer depends on that marker: the poll reloads it.

## Verification

| Check | Result |
| --- | --- |
| `npm run build` (tsc + Vite) | `dist/assets/index-73IklX0x.js` 843.09 kB, no type errors |
| `npx vitest run` | 41 files, 240 tests passed |
| `pytest tests/test_route_collections.py` | 4 passed |
| `py_compile operon/library_install.py src/web/library_api.py` | passed |
| `build_runtime.py --mode management` | `Operon 5.4.6`, `application_version` 5.4.6 |
| `build_setup.py` | `ProductVersion` 5.4.6, payload audit clean |
| `dotnet build tests/native_setup` and `SetupTests.exe` | 97 native installer checks passed |
| Installation, upgrade and UI behaviour | performed by the requester |

## Artifacts

| Asset | Size (bytes) | SHA-256 |
| --- | --- | --- |
| `Operon_Setup-5.4.6.exe` | 428,848,286 | `c29fffaa8bed82bb1ece902b7302e18eb7bb95001a8bb15d4781179f8dfd41a5` |
| `Operon-5.4.6-Server.zip` | 4,671,963 | `a5d3dfffdb2d154f6cbafac14ae952569d7a378bee773c2303d13cec9e812c11` |
| `operon_studio-5.4.6-py3-none-any.whl` | 978,520 | `5177cba5b8aacbdeb0fa2547792cc1f9187ad007070624f685bdef7089731d4a` |
| `SHA256SUMS.txt` | 282 | `269088a041e89eca7bab264c51a6f87066622234d61c3535b1c5a82eb3d4d937` |

## Upgrading

Install 5.4.6 over 5.4.5. Operator libraries and route libraries stay where they
are; the route collections recorded from now on are listed in the import panel.
An installation whose `versions` directory is empty because of the 5.4.4 defect
can be repaired by installing 5.4.6 again: the installer no longer sweeps the
version it just promoted.

## Known limits

- Removing a route collection deletes the routes it created, including their
  saved graphs; routes imported separately are untouched.
- The side panel still counts routes as part of the operator badge, so the number
  changes when routes are imported or removed.
