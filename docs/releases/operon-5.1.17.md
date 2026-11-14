# Operon Studio 5.1.17

Released 2026-11-14. Application-only release; the operator library stays at
0.1.2 and is installed separately from an `operon-library-v0.1.2.operon-library.zip`
bundle.

## Library refresh after deleting a library

`PluginManager.refresh()` no longer falls back to the legacy source-tree seed in
5.x installations. The application no longer ships
`operon/builtin_packages.json`, so the old fallback raised:

```text
[WinError 2] The system cannot find the file specified:
...\operon\builtin_packages.json
```

`ensure_source_root()` now seeds only when the application root contains
`operon/builtin_packages.json`. When a managed source tree has no editable
library, `refresh()` returns a no-op result with the message
`No editable operator library is installed` instead of copying from the
application root. Deleting the last installed library followed by Refresh is
therefore safe.

## UTC+8 timestamps

History rows, event logs and collaboration activity are formatted in
`Asia/Shanghai` and labelled `UTC+8`. Event log times use a 24-hour clock.

## Verification

- `tests/test_plugins_refresh_517.py`: 1 passed.
- `tests/test_plugins_refresh_517.py tests/test_library_release.py`: 10 passed.
- Frontend: 34 files / 213 tests passed; `tsc -b` and the real Vite production
  build succeeded. The built bundle contains `5.1.17` and `UTC+8`.

## Compatibility

- Operator library: 0.1.2 (`minimum_application` 5.1.6).
- Application protocol: v3, revision 3.7.
- No library or route bundle format change.
