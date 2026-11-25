# Operon Studio 5.9.5 test report

## Scope

5.9.5 changes one constant in `operon/library_bundle.py` and adds one
regression test. Nothing else in the application or library changed; the
library stays at 2.0.0.

## Evidence

| Check | Result |
| --- | --- |
| `pytest tests/test_library_upgrade_compat.py tests/test_library_environment_manifest.py -q` | 9 passed |
| Managed installer source branch (5.9.4) with the gate in place | failed with `Operator library 2.0.0 is too old for Operon Studio 5.9.4; version 8.0.10 or newer is required` |
| Managed installer source branch (5.9.5) | exercised through the desktop UI (设置 -> 服务端维护 -> 强制升级服务端); the run log is recorded in the session operations log |

## What is not claimed

The artifact hashes and the UI acceptance run for this build are recorded in the
session log and release checksums, not inferred here. No operator behaviour
changed, so the 1074-operator / 110-reader catalog coverage is unaffected.
