# K03–K12 development acceptance record

Dates: 2026-11-14–15 (Asia/Shanghai). Branch: `backend/5.1.9-cluster`.
Base: `600eed6f53b6db01f7391f408ade1e950d8679b3`. Application: **5.1.9**.
This records inspected development evidence, not a complete gate or release
approval. No operator library changes, version bump, commit, push or publication.

## Actual environments

- Windows 11: management CPython 3.12; actual isolated scientific CPython
  3.11.15, R 4.4.2 and a compiled C executable.
- Linux: one provider container, 0.5 CPU / 1 GiB, reached through the authorized
  web terminal. Independent CPython 3.11.14 and a hash-locked wheelhouse were
  prepared under an isolated test directory. System Python was not replaced.
- PostgreSQL: actual 17.12 process on Windows loopback, owned data directory,
  stopped after verification. No external database service was changed.
- No second host, Slurm allocation or successful native SSH/SFTP transport.

## Evidence by scope

Paths below are relative to `verification/backend/`; failed diagnostic runs
remain preserved. Overlapping tests are not added into a single inflated total.

| Evidence | Outcome | What it establishes |
|---|---|---|
| `contract-q.xml` | 106 passed | RunPlan/contracts, frozen values, authoring-v2 and portable metadata regressions |
| `bindings-fix-l.xml` | 88 passed, 1 skipped | Owned producer/consumer bindings, host receipts and bounded cluster boundary regressions |
| `cwd-alias-n.xml` | 17 passed | Exact Windows attempt-directory aliases and confinement |
| `languages-t.xml` | 22 passed, 1 failed | Real moved native Reader/operator package and native Form → Python passed; the original R path failure was real and was not counted as acceptance |
| `languages-z.xml` | 21 passed | Actual Python → R → C → Python, branch/join, resume, edited independent parameters and physical-path guard tests |
| `foreign-runtime-acceptance.json` | Results 63 then 57; 8 environment and 8 capacity leases released | Empty PATH / clean HOME, unchanged immutable payload, Windows Job Object exit proofs; explicitly short physical work directory |
| `preparation-x.xml` | 46 passed, 1 failed | Preparation failure/ambiguous-launch tests passed; positive host test exposed an additional long-path resolver failure |
| `resolver-final.xml` | 28 passed, 1 skipped | Corrected long-path publication read plus actual host producer/consumer/dedupe/cancel, after preparation-proof changes |
| `launch-lock-final.xml` | 3 passed | Launch-lock acquisition/release failures retain ownership and grants, including an already spawned worker |
| `stop-ownership-final.xml` | 2 passed | A live launch thread blocks coordinator ownership release; pool shutdown preserves its handles and supports retry |
| `results-u.xml` | 53 passed, 3 skipped | Bounded shared plan result reads and delegation; Windows denied three link fixtures, so no claim from those skips |
| `postgres-real-c/` | 11 passed, process stopped | Actual transactional admission/replay/rollback, leadership, migrations, quotas and cancellation intents |
| `frontend-build-q.log` | Build passed | TypeScript/Vite product bundle builds; existing bundle-size warning remains |
| `frontend-library-p.log` | 13 passed | Correct metadata-owned import request assertion; no library implementation changed |
| Linux `linux-a.xml` | 241 passed, 5 skipped | Environment/contracts/YAML/invocation/storage/plan/cluster boundaries on Linux |
| Linux `linux-e2e.xml` | 1 passed, 3 failed | One-host real producer/consumer/cancel passed; three portable tests exposed missing Linux containment helper |
| Linux `linux-c.xml` | 77 passed, 2 skipped | Corrected moved portable script branch/join, injected failure and verified resume, native Reader/operator and Form boundary; result read/retention/collector regressions |
| Linux `linux-e.xml` | 54 passed, no skips, 105.44 s | Real delayed-monitor/early-cancel/fenced-readiness cases, launch rejection/lock receipts, retryable coordinator shutdown and actual host native producer → Form → Python consumer plus immediate cancellation |
| `wheel-final/verification.json` | Development wheel built and payload checked | Required schemas, SQL migrations, containment/path helpers present; not Setup or release acceptance |

Linux source D produced 65 passed, 4 skipped and 1 failed. Its real producer and
consumer succeeded; immediate cancellation killed the Linux monitor with SIGTERM
before its handler was ready. No tree-exit proof was emitted, and leases were
correctly retained. Source E's fenced monitor-ready handshake and cancellation
protection passed all 54 focused cases, including the real host workflow. Source
D remains a preserved failed diagnostic, not an accepted final gate. Readiness
is bounded at 10 seconds; a target that cannot confirm readiness in that window
is quarantined with resources retained, not automatically rerun.

## Source and payload identities

Linux source archives contain only selected code/configuration/tests and unchanged
seed files, plus `ACCEPTANCE_SOURCE.json` with each selected source hash. They
exclude credentials, local profiles, environments and user data.

- Source B: `aaa79f50a39631b0f05528683722fb28ebdf0bfee3c936d9d3596c7b9573d5fc`.
- Source C: `5fe4e42154255087e487681e94437e4f5dc76a932f0076d3e4ff735d2f6c8a2c`.
- Source D: `fa8d18ec4d753247b6a1236566cbc006ff59590e709b70374df996bb0e30d7c9`.
- Source E is source D plus patch `b10aa42ffe3970d6748c5c6b3474ff0f8a34c0df50c8d1b739ad62db494e35f5` (10 selected files and a per-file hash manifest).
- Development wheel: `5fd3799cb3b7f3404e98846acc66034357876e72d3cea6effb24cb78ca8ceff9`.
- Linux evidence ZIP: `9f27d1dc4da33077b847691e260812d4968950aeb290f6537df5d2e59cfeebce` (1,338,261 bytes). Contains failed diagnostics and final successful checks separately; it must not be interpreted as every historical test passing.

The development wheel keeps version 5.1.9 and lives only in the verification
directory. It must not replace a published 5.1.9 asset. No Setup or public Linux
release archive was produced from this checkout.

## Important observed fixes

1. Preserve canonical extended Python executable spelling even when only its
   loaded binary-module path is long.
2. Include lazily accessed Context/SDK code and Linux containment in the explicit
   portable kernel; reject case-insensitive attribute/module false matches.
3. Replace explicitly supplied frozen parameter entries, rather than merging
   current defaults back into a saved route.
4. Read committed long-path metadata without weakening confinement, open-handle
   identity or content verification.
5. Persist a fenced atomic no-spawn outcome for failures before the supervisor
   launch boundary. Missing/ambiguous evidence remains recovery-required.
6. Reject unsupported Windows R physical layouts before launch. No hidden
   relocation, permission retries, new lease authority or user-result cache.
7. Require the Linux subreaper's fenced readiness receipt before publishing a
   running attempt, opening its start gate or signalling it for cancellation.
   Timeout, wrong identity and early monitor death preserve environment pins.
8. Do not relinquish coordinator ownership after a timed join while its launch
   thread is still alive. Preserve the pool handles and allow shutdown retry.

The final Linux host database contains two completed runs and one cancelled run;
all three attempts have released capacity leases. Their environment leases and
subreaper tree-exit receipts are archived. The final evidence collector observed
no live owned pytest/monitor/worker processes. Deliberate malformed-proof and
earlier failed-run records remain preserved; their retained pins are diagnostic
evidence, not silently rewritten into successful releases.

The ZIP was downloaded into `verification/backend/linux-evidence/` and its local
SHA256 matched the server. It contains 386 files. `linux-a` skipped the missing
MCP package and four Windows-only filesystem cases; `linux-c` skipped two MCP
adapter cases because MCP was absent from the Linux management test environment.
The final lifecycle group had no skips. Pytest's `hostcurrent` alias appears in
the database summary as well as `host0`; they are the same database, not two hosts.

The provider console confirmed the current instance `rR5xaro7` was shutting down,
with billing paused and zero running instances. Screenshot:
`verification/backend/linux-evidence/server-shutdown.jpg`. This is the observed
console state; no older instance's shutdown API was used.

## Remaining gates

- Real two-host SSH/bastion placement, shared/remote storage bindings and
  failover; one host was available. Web terminal operation is not SSH acceptance.
- Actual Slurm submission/accounting/cancel and site resource enforcement.
- Fully integrated cluster controller + host transport fault/load testing.
- Complete StorageRef input-selector/execution wiring, new RunPlan human-facing
  workflow and committed artifact file previews/downloads/third-party viewers.
- Full automatic target-native R/native dependency resolution and toolchain
  closure; actual locked fixture runtimes do not prove arbitrary dependencies.
- Windows Setup/shortcut and exact Linux release-package acceptance (K12).

See `backend_k03_k12_progress.md` for the module/product/actual-gate separation,
`backend_cli_quickstart.md` for executable development examples, and
`windows_foreign_runtime_paths.md` for the supported R placement contract.

