# Operon 5.9.2 test report

## Release identity

| Item | Value |
| --- | --- |
| Application | 5.9.2 |
| Operator library | 2.0.0 (unchanged) |
| Operators | 1074 |
| Readers | 110 |
| Routes | 79 |
| Release assets | `Operon_Setup-5.9.2.exe`, `Operon-Studio-v5.9.2-Windows-x64.zip`, `Operon-5.9.2-Server.zip`, `operon_studio-5.9.2-py3-none-any.whl`, library bundle/wheel, routes archive, two `SHA256SUMS` files |

## Registry

```
registry build --scope packages : 1074 operators, 110 readers, 7 packages, 0 errors
registry build --scope routes   : 1074 operators, 110 readers, 79 routes, 0 errors
registry check --scope packages : changed [], errors []
```

The registry is byte-identical to 5.9.1 apart from the application version
fields, because 5.9.2 only changes the remote transport.

## Unit tests

| Suite | Result |
| --- | --- |
| `tests/test_remote_handshake.py` + `tests/test_remote_installation.py` | 46 passed |
| `tests/test_remote_cleanup.py` + `tests/test_remote_upgrade_retire.py` + `tests/test_remote_provision.py` | 24 passed |

## Defect reproduction and fix

Before the fix, a managed server installed at
`/public/home/lihj/Operon/managed-v1/code-c27107338b5cd5a0ce66` reported:

```
operon-ready.json build        : {}
build_identity(code tree)      : build_id 8761e8a9…, source f1b4c199…, library "", operators 0
desktop / provisioning receipt : build_id 3913ccbd…, source c2710733…, library 96eef2ac…, operators 1074
```

`operon.build_identity.matches()` compares `build_id`,
`application.source_sha256` and `library.bundle_sha256`, so the handshake
raised `stale_build` and the desktop refused to connect even though the
deployment itself succeeded.

After the fix, the installer writes the expected identity into the receipt and
the handshake prefers the provisioning receipt over a recomputed digest. The
new unit tests cover both helpers (`managed_build`, `receipt_build`) and the
managed transport keyword set.

## Manual verification plan

1. Install `Operon_Setup-5.9.2.exe` on a clean directory.
2. From the headed UI, force-upgrade the `licai-srv` managed server.
3. Connect; the status panel must show the server as connected and the
   capability/environment snapshot must load.

## Limitations

- The fix is server-side code delivered in the desktop payload; an already
  upgraded server needs one more upgrade from a 5.9.2 desktop.
- No operator behaviour changes, so the 5.9.0 operator evidence still applies.
- No remote server was upgraded as part of building or publishing this
  release.
