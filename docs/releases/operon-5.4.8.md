# Operon Studio 5.4.8

Released 2026-11-18.

5.4.8 makes route collections portable: importing a collection resolves
operators by id against the installed library instead of requiring the exact
pins the collection was compiled with.

## Fixed

- **Route collections import by operator id.** A route bundle carries
  `plugin_lock` entries with `package`, `version` and `code_sha`. A wheel
  descriptor also carries the wheel `sha256`, and `pins.identity()` used all
  four keys, so a bundle pin could never equal the installed implementation.
  Registering the route then asked `plugins.snapshot` to resolve the pins and
  aborted with:

  ```
  Required plugin versions are unavailable; install the original packages.
  Unknown or wheel pins are not automatically replaced.
  ```

  Import now calls `strip_pins`, which clears `plugin_lock` on every graph part
  (including graphs nested in route nodes), and keeps the removed pins in the
  collection manifest at `<workspace>/.studio/workflows/collections/<slug>.json`
  as provenance. The graph is stored and run without pins, so the installed
  library is the single source of truth.
- **Both import paths behave the same.** `POST /api/routes/import-collection`
  and `POST /api/v1/routes/import-archive` no longer reject a bundle because a
  pin does not match. The archive endpoint records the stripped pins in its
  `migrations` list instead of failing with `Unable to prove pin
  correspondence`.
- **Canvas behaviour is unchanged.** 5.x canvas graphs never carried pins and
  `_verify_pins` stays a no-op, exactly as in 5.1.17. The gate that rejected
  collections lived in the catalogue lookup performed at registration time.

## Route collections are user-authored

An official pack is not required and no signing step exists. A collection is a
ZIP with `routes.json` and one workflow bundle per route; the only compatibility
requirement is that every operator id it uses exists in the installed library.
Package names, library versions and wheel hashes do not have to match.
`docs/design/route-collections.md` documents the format, the provenance fields
and how to author a collection against a specific library version.

## Verification

- Clean install of `Operon_Setup-5.4.8.exe` in a fresh `--install-dir` on D:
  (version directory `5.4.8-477f6e26723a`), backend ready in 33 s.
- The bundled base library installed on first start: `main-v0.1.28`,
  7 packages, 1069 operators, 108 Readers, 1177 descriptors.
- `POST /api/routes/import-collection` with
  `operon-routes-main-v0.1.28.zip` returned `200` and `count: 79`; every route
  name was returned.
- Manifest check: 79 routes, all 79 with `pins` recorded. Stored graphs:
  79 route files, 0 with `plugin_lock`.
- Regression tests: `tests/test_route_pin_strip.py` 3 passed (top-level strip,
  nested route graph, collection import keeps pins as provenance).
- Frontend: 41 files / 240 tests passed. Runtime reports `Operon 5.4.8`.

## Artifacts

| Asset | Bytes | SHA-256 |
|---|---:|---|
| `Operon_Setup-5.4.8.exe` | 428,850,998 | `84aeaba2400106ab1ac6f0381c48f672df4d8a89e9970967e5caba9896f4c87c` |
| `Operon-5.4.8-Server.zip` | 4,674,610 | `7f4d7b7f4dc0d1e03862afdbc024ba4ce84dac6616e2a89b1cf6bc8b315655b7` |
| `operon_studio-5.4.8-py3-none-any.whl` | 978,496 | `f639f608be395f1f248dc52a6334fbe512474d5ac4e5e2353beabb9469d03710` |

The Windows payload is `Operon-Studio-v5.4.8-Windows-x64.zip`
(25,585 files, 357,073,759 bytes,
`80bbb330b6003dd87af9e618c5c95570f26e3ba13f401fd9c57d5c8ae5ea7b93`) and is
embedded in the installer.

## Upgrading

Install over 5.4.7. Routes imported before 5.4.8 keep working untouched;
collections that failed to import can be imported again after the upgrade.
Library version and contents are unchanged (`main-v0.1.28`).

## Known limits

- Recorded pins are provenance only. They are not enforced at run time, and a
  future library revision that removes an operator will make routes that use it
  fail with the missing operator id, not with a pin mismatch.
- Collections that reference operators absent from the installed library still
  fail at import; the error lists the missing ids.
- Route library packages cannot be upgraded in place; remove the collection and
  import the new one.
