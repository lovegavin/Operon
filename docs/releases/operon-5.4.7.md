# Operon Studio 5.4.7

Released 2026-11-17.

5.4.7 fixes the operator palette so it always reflects the library source you
selected, and stops the desktop host from failing the first launch while the
bundled operator library is still being installed.

## Fixed

- **The palette follows the library you are browsing.** The operator palette
  used to merge the catalog of the selected server (which is often offline, or
  loaded from a cached snapshot) in front of the local catalog and then union
  every other catalog on top. Local imports and removals were therefore only
  ever added, never removed: the sidebar count stayed frozen at the server
  snapshot (for example `1340` = 1070 operators + 108 Readers + 162 routes)
  even after a library had been installed or deleted locally, and `Ctrl+R`
  could not change it because reloading re-merged the same snapshot.
  The palette now renders exactly one source.
- **Library source selector.** The operator panel header has a new
  `Library source` selector next to `+`. `This machine` is the default; each
  configured remote profile is listed as well and marked `offline` when its
  connection is not established. The palette count, the Readers section and the
  operator list all follow the selected source.
- **The round button reloads the catalog.** The circular button next to `+`
  previously opened server settings whenever a server was selected. It is now
  `Reload operator library`: it re-reads the backend catalog, pushes the result
  through `CatalogUpdates.force`, and reports `Operator library updated.` or
  `Operator library is up to date.` It never navigates away from the canvas.
- **First launch no longer times out.** The desktop host waited 90 s for the
  backend to report ready. On a cold disk the bundled base library
  (`main-v0.1.28`, 1177 descriptors) can take longer than that to expand and
  register, so the window failed with `System.TimeoutException` while the
  backend kept running. The host now waits 300 s
  (`desktop/Program.cs:207`).
- **A cleared library folder is repaired on start.** `_bootstrap_base_library`
  returned early whenever `base-library.json` existed, even if the library
  registry had been emptied. The marker is no longer treated as proof that the
  library is present.

## Verification

Installed `Operon_Setup-5.4.7.exe` into a clean directory and drove the real UI
through the DevTools protocol:

- First launch reached a usable backend in 54 s; the window opened and the
  sidebar showed `1177` (1069 operators + 108 Readers + 0 routes), matching
  `GET /api/libraries` (`main-v0.1.28`, 7 packages, 1177 descriptors).
- Importing `operon-library-fork1-v0.0.0.operon-library.zip` through the import
  dialog changed the badge `1177 -> 1178` and reported
  `Imported operator library v0.0.0: 1 operator / Reader.`
- Deleting that library from the management tab changed the badge
  `1178 -> 1177` within ~8 s and reported
  `Removed operator library fork1-v0.0.0.`
- Clicking the round button produced `Operator library is up to date.` and did
  not open server settings.
- The library source selector listed `This machine` and kept rendering the local
  catalog.
- Frontend: 41 files / 240 tests pass; desktop build reports
  `ProductVersion 5.4.7`; native installer checks `PASS: 97`.

## Artifacts

| Asset | Bytes | SHA-256 |
|---|---:|---|
| `Operon_Setup-5.4.7.exe` | 428,848,873 | `df09e33d348398d38e3ec04c30a4674f15b91e065f3209b5bba64c17f20b45e6` |
| `Operon-5.4.7-Server.zip` | 4,672,312 | `8e39781afbbb94257f68c71810ec3ec7d5e0073bf4702b83a14ff2f7e7bb8535` |
| `operon_studio-5.4.7-py3-none-any.whl` | 978,602 | `52dcc202993441c1712ed71ac28245b21581bf0a1739e70f123bb35eefe1b1e6` |
| `SHA256SUMS.txt` | 283 | `d012cf8ff1e98e4e979af8b650525bf69a4745e230fbf09544d38c28b70c09c5` |

## Upgrading

Install over the previous version. Libraries installed under
`<install>/versions/<version>/library` are version scoped, so the bundled
`main-v0.1.28` is installed again for the new version on first launch; the 300 s
host timeout covers that pass. Workspace documents, routes and remote profiles
are unaffected.

## Known limits

- The palette reflects a remote source only while that server is connected; an
  offline server is shown as a source but its snapshot may be stale.
- Route collections are imported and removed per collection
  (`GET`/`DELETE /api/route-collections`); individual routes inside a collection
  are still not removable one by one.
