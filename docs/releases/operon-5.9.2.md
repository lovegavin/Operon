# Operon 5.9.2

## Overview

5.9.2 makes a managed server usable again after it has been upgraded. The
previous release could install the new server successfully and then refuse
every client connection with `stale_build`, because the server reported a
build identity that could never match the desktop's.

## Defect

`operon/remote/install_linux.py` received the build identity the desktop
deployed (`--build`) but only used it when the uploaded code tree carried a
`library/` directory. The managed code tree does not: the operator library is
installed into the workspace. The readiness receipt therefore recorded
`"build": {}`, and `operon/remote/handshake.py` fell back to computing a tree
digest that cannot see the workspace-installed library and does not hash the
same file set. The resulting identity differed from the provisioning receipt,
so `operon.build_identity.matches()` failed and the client raised
`服务端代码或算子库与桌面端不一致；请安装 / 升级服务端后再连接。`

## Fix

- `install_linux.py` records `identity or expected` in the readiness receipt,
  so a receipt is never empty when the desktop supplied an identity.
- `handshake.py` reads the build from the managed provisioning receipt
  (`<managed root>/server.json`) before recomputing a tree digest, so a server
  that was installed from a desktop payload reports the deployed identity.
- `tests/test_remote_installation.py` now expects the `force` keyword the
  managed transport already passes (the assertion had lagged the feature).

## Compatibility

- Application code only; the operator library stays at 2.0.0.
- A server upgraded before 5.9.2 must be upgraded once with a 5.9.2 desktop
  before it can accept connections again.

## Verification

- `tests/test_remote_handshake.py tests/test_remote_installation.py` — 46 passed.
- `tests/test_remote_cleanup.py tests/test_remote_upgrade_retire.py
  tests/test_remote_provision.py` — 24 passed.
- Registry unchanged: 1074 operators, 110 readers, 79 routes, 0 errors.
- Manual: force-upgrade a managed server from the desktop and connect.
