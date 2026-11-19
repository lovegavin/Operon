# Operon Studio 5.7.5 test report

## Scope

5.7.5 fixes four progress and cancellation defects reported against 5.7.4:

- F-64: a preparation with no reported bytes showed a hard 0% bar that never moved.
- F-65: remote cards stopped updating after an action, so an installation could sit at 52% forever.
- F-66: cancelling an environment that had already been committed rewrote its state to cancelled and then flipped back to installed.
- F-67: pip download progress was invisible, and the periodic disk sample overwrote the parsed byte count.
- F-68: cancelling an environment that was not preparing returned HTTP 404 instead of a readable outcome.

## Builds

| Artifact | Size | SHA-256 |
| --- | --- | --- |
| Operon Studio 5.7.5 payload | 357,500,238 | 3fcdc87161b825ca09d4424673bfbd16987a16487381c819a6ec7c43b0afb90f |
| Operon Setup 5.7.5 | 429,277,594 | 14afef88d7f56f8674440f023f02cfda4684321ee669f7a7a1655f302e02ed4f |
| Operon 5.7.5 server bundle | 9,829,778 | 2b2d9834202030b39ac93730300e2c1a7b48e7c5081dd025cf8bbc2fc90cfbb1 |
| Application wheel | 998,695 | 6330f326dd448486ce26507ab1739d8742979e6ac40e517c6e9ea3fe9deb593e |
| Library 1.1.3 | 6,993,483 | f1337340d8a909c8fb5e199cf91c1e24919b9128f6dd64636a486b7a8f9a9fb0 |
| Route collection 1.1.3 | 201,389 | 9a5cb56b405cd0cb657c546d7eba90ff8a78c86901c8c6bd6c32dbe90e61dda9 |

The library is unchanged from 5.7.3; only application code moved, so the library release is not re-published.

## Clean installation

| Check | Result |
| --- | --- |
| Installer result | installed |
| Version directory | 5.7.5-4ceceb03207e |
| Version endpoint | 5.7.5 (4ceceb03) |
| Environments | 18 |
| Server ready after start | 32 s |

## Cancellation and progress

| Scenario | Observed |
| --- | --- |
| Progress before any byte lands | phase creating, bytes 0, expected 145,000,000; the panel now renders an indeterminate bar instead of 0% |
| Cancel while creating | HTTP 200, completed false, cancelled true; environment returns to missing within five seconds |
| Cancel after the environment is ready | HTTP 200, completed true, cancelled false, reason "该环境已完成安装，取消无效。"; environment stays ready |
| Cancel with nothing running | HTTP 200, completed false, cancelled false, reason "没有正在进行的准备任务。" |

## Interface parity

- The cancel request is routed through the remote agent when the execution location is a server.
- The log dialog requests the remote log endpoint when a remote target is selected.
- The remote card list is refreshed on the same three second cadence as the local list.

## Automated checks

| Suite | Result |
| --- | --- |
| tests/test_environment_install.py | 16 passed |
| tests/test_environment_api_runtime.py | 9 passed |
| tests/test_environment_requirements.py | 3 passed |
| Frontend suite | 43 files, 265 tests passed |
| TypeScript build | clean |

## Known limitations

- The live remote session was exercised through the remote manager tests; a remote installation was not observed end to end in this build.
- Byte reporting depends on pip printing download sizes; phases that only create files still show the indeterminate bar.

## Not tested

- Very large weights downloads were not re-run in this build.
- The 1,073 operator coverage sweep continues in a separate installation and is not part of this report.
