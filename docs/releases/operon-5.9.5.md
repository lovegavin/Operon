# Operon Studio 5.9.5

5.9.5 fixes the version gate that stopped a managed server from installing the
bundled operator library.

## The defect

`operon/library_bundle.py` declared `MINIMUM_LIBRARY_VERSION = '8.0.10'`, a value
left over from a release line whose library was numbered 8.x. This branch ships
the library at 2.0.0, so every `install_source` / `install_bundle` call raised:

```
Operator library 2.0.0 is too old for Operon Studio 5.9.5; version 8.0.10 or newer is required
```

The managed server reached that call because 5.9.4 made the source archive carry
`library/pyproject.toml` and `library/seed`, so the installer took the source
branch and built its own registry, library manifest and operator catalog. The
gate then rejected the very library the application ships.

## The fix

`MINIMUM_LIBRARY_VERSION` is now `2.0.0`, the first library line that speaks the
port-rule protocol. A regression test compares the constant with
`library/release.json`, so the gate can no longer drift away from the shipped
library.

## Verification

- `pytest tests/test_library_upgrade_compat.py tests/test_library_environment_manifest.py -q`
  -> 9 passed.
- The managed upgrade path (UI: 设置 -> 服务端维护 -> 强制升级服务端) is exercised
  end to end after this build; results are recorded in the test report.
