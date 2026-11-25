# Operon 5.9.4 test report

## Scope

Managed deployment library delivery and build-handshake logging.

## Results

| Check | Result |
| --- | --- |
| `python3 -m pytest tests/test_remote_provision.py -q` | 15 passed in 1.33s |
| Archive content (repo tree) | 3,869,690 bytes, 4,451 files, `library/seed/src/task/step/steps` present |
| Identity parity (desktop vs extracted archive) | equal — `bundle_sha256 96eef2ac0234a706ff8a0b8120c14f8921b6f523666c9d7c63df9fad0bb96a4c`, `library_version 2.0.0`, 7 packages, 1184 descriptors |
| `__pycache__`/`.pyc` exclusion | covered by the new unit test |

## Not yet verified at report time

- End-to-end upgrade of `licai-srv` from the installed 5.9.4 desktop through
  the real UI button (设置 → 服务器 → 服务端维护 → 强制升级服务端), and the
  resulting `GET /api/remote/{key}/environments` listing the 20 environment
  trees. This is the acceptance step for the release and is appended here once
  the run completes.

## Regression notes

The earlier 5.9.3 attempts failed with `本地程序在准备期间发生变化，请重试。`
because a 7.1 MB library bundle was copied into the installed version directory
after the desktop had connected, changing the archive digest and the build id.
That was an operator error, not a product defect; the new log line now records
both ids so the cause is visible in the setup log.
