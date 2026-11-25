# Operon 5.9.1

Patch release. Fixes the failure that stopped a desktop from upgrading a server
whenever a shared pool process existed without an `instance.json` record.

## The defect

`operon/remote/provision.py` uploads a retire script before replacing a remote
installation. That script reused one name, `directory`, for two different
values: the control-socket directory at the top of the script and the pool
record directory inside the shared-pool loop. A pool process discovered through
`/proc` has no record file, so the loop assigned

    directory = os.path.dirname(record) if record else None

and the later control-socket join raised

    TypeError: expected str, bytes or os.PathLike object, not NoneType

The desktop reported this as "无法检查旧版服务端；为避免覆盖运行中的任务，升级已停止。"
No file on the server had been modified, because the retire step runs before
the new code is uploaded.

## The fix

- The control-socket directory is now `socket_dir`; the pool record directory
  is `pool_dir`. The pool loop can no longer clear the socket path.
- `tests/test_remote_cleanup.py` gains a regression test that spawns a pool
  process visible only in `/proc` (no `instance.json`) and a fake server process
  whose working directory is under the fake home. The script must exit 0 and
  print `BP_RETIRE_RESULT`. The pre-fix script exits 1 with the same TypeError.

## What changed

- `operon/remote/provision.py` (retire script variable names).
- `tests/test_remote_cleanup.py` (regression test and updated assertions).

## What did not change

- Operator library stays at **2.0.0**; no library asset is rebuilt or republished.
- Registry is unchanged: 1074 operators, 110 Readers, 79 routes, 0 errors.
- Port rule, operator declarations and workflow JSON are untouched.
- No remote server is upgraded by this release. Install it and use
  "安装 / 升级服务端" to deploy.

## Verification

- `pytest tests/test_remote_cleanup.py tests/test_remote_provision.py tests/test_remote_upgrade_retire.py` -> 24 passed.
- Reproduction against the pre-fix script: exit code 1,
  `TypeError: expected str, bytes or os.PathLike object, not NoneType`.
- Same scenario against the fixed script: exit code 0 with `BP_RETIRE_RESULT`.
- Payload, Setup, Server bundle and both wheels are built from commit
  `b5653075f` and checked by the 5.9.1 acceptance script (`problems: []`).
