# Non-library backend issues (BE-03/04/05/07/08/09)

This document separates the issues in `backend_issues.md` that are **not** operator
library (`library/seed`) defects from the three that are.

- Library-owned and therefore excluded here: **BE-01, BE-02, BE-06**.
- This document covers the application/runtime layer: **BE-03, BE-04, BE-05,
  BE-07, BE-08, BE-09**.
- Baseline for the code reading: git tag `v4.0.4`
  (`17428b68b4853505bf816d76bb5aed2726a6e1`), worktree
  `/home/gavin/Operon-404`. BE-03/04 were re-checked against current `main`
  (Studio 4.0.5). The report's installed directory name
  `4.0.4-30b4f1538cbb` does not exist locally.

"Application layer" here means `operon/`, `src/web/`, and the MCP server. A fix
requires an application release, not a new operator-library bundle. Operator
metadata and operator contracts are covered in
`docs/verification/backend-issues-4.0.4-audit.md`.

## Summary

| ID | Verdict | Owner | Fixable without a library change? |
| --- | --- | --- | --- |
| BE-03 | confirmed (mechanism) | admission | yes |
| BE-04 | confirmed (code path) | job service / engine | yes, but larger change |
| BE-05 | confirmed (mechanism) | readiness / graph locking | yes |
| BE-07 | partial | execution-target schema, path policy, docs | yes, partly UX/docs only |
| BE-08 | confirmed | remote service / MCP | yes |
| BE-09 | partial | MCP views / documentation API | yes, partly client-side |

## BE-03 — disabling memory reserves the whole host process limit

**Type:** application admission bug.

Evidence:

- `src/web/admission.py:220-246`: `enabled = memory.get('enabled', True)`.
- When `enabled` is false the request sets
  `budget, reserved, cpus = 0, self.capacity, self.cpus`.
- `process_limit_bytes = min(reserved, ...)` therefore equals the host process
  limit, not zero.
- `operon/engine/contracts.py:259` computes
  `schedulable_bytes = ceiling_bytes - management_reserve_bytes`.
- `operon/engine/policy.py:166-177` marks a unit whose `ram` exceeds that capacity
  `infeasible_resources`.
- `operon/engine/coordinator.py:639-649` writes
  `The unit minimum exceeds the frozen pool ceiling`.

This explains the report's numbers: unit `process_reservation_bytes=203149342310`
equals the pool ceiling, with `management_reserve_bytes=10157467115`; admission is
infeasible while `job.json` stays queued. Enabling memory changes the reservation
path and the same graph completes 10/10.

Proposed fix:

- When `memory.enabled` is false, use `reserved = 0` and `budget = 0`; keep CPU
  allocation independent (`min(self.cpus, max(1, requested_threads))`).
- Do not let a zero-memory request consume the pool's process reservation.
- Add a regression test with memory disabled that asserts admission succeeds and
  the allocation has a zero process reservation.

Risk: low. It changes scheduling for all memory-disabled runs, so test the
legacy/no-memory path and the existing memory-enabled path together.

## BE-04 — coordinated parent jobs keep `queued` after a child failure

**Type:** application job-state integration bug, likely in the coordinator path.

Evidence:

- `src/web/service.py:664-700` creates a job as `queued` with
  `queued_reason='Waiting for available host memory and CPU'`.
- `_submit_coordinated` (`src/web/service.py:728-758`) calls
  `engine.facade.submit(...)` and returns; it does not copy a terminal engine
  status back.
- `_refresh_jobs` (`src/web/service.py:462-560`) reconciles local owner/worker
  process state only. It does not read an engine run/attempt terminal state.
- `_start_coordinated` (`src/web/service.py:1005-1030`) runs only after the
  coordinator commits a lease. If admission fails before that, no callback sets
  the parent to `failed`.

This matches the report: parent `job.json` remains `queued`, the child
`req-f52429db4744c975fbbcb7c6` is failed, and `launcher.events.jsonl` contains only
`job_queued`. The completed sibling job is not evidence against the missing failure
path.

Proposed fix:

- When the engine rejects admission or a child attempt reaches a terminal failed
  state, write the parent `job.json` once with `status=failed`,
  `error`/`finished_at`, `logs_complete=true`, and the admission reason.
- Alternatively, add a status reconciliation in `_refresh_jobs` that maps engine
  run/attempt state to the parent record, idempotently.
- Keep the state transition under `self.lock`; do not release a reservation twice.

Risk: medium. This touches job lifecycle and concurrency. Test admission rejection,
child failure after acceptance, cancellation, and duplicate refresh passes. A live
coordinator replay is required for final confidence; the remote host was
unreachable during this audit.

## BE-05 — readiness is not bound to the current fingerprint

**Type:** application readiness / lock-maintenance bug.

Evidence:

- `operon/readiness.py:365-369` (`require_ready`) checks only
  `readiness.get("status") != "ready"`; it never compares the stored
  `fingerprint` with the graph being launched.
- `operon/readiness.py:77` and `src/web/execution.py:581` prune `plugin_lock`
  against currently used operator ids only during validation/staging.
- `operon/plugins.py:304-317` adds pins for active nodes but never removes obsolete
  entries.
- No path was found that rebuilds `plugin_lock` from live nodes on every canvas
  add/remove/update.

So a 27→21→11 node edit can leave join/aggregate/export/interface pins in the
lock, change the environment fingerprint, and fail `operon_run` with
`environment_not_ready` after the smaller graph prepared successfully.

Proposed fix:

- In `require_ready`, compare the current graph fingerprint with
  `readiness["fingerprint"]`; on mismatch return `environment_not_ready` with both
  fingerprints and require a fresh prepare.
- In the graph save/pin path, rebuild `plugin_lock` from the live node set (and
  nested route graphs), not from the previous lock.
- Add tests for add/remove/update on a graph containing a route node and for a
  cached readiness record with an old fingerprint.

Risk: medium. Rebuilding the lock can invalidate cached readiness and force
re-preparation; that is the intended semantic, but it must not drop pins needed by
nested route graphs.

## BE-07 — execution target and path strictness

**Type:** mixed. Some behavior is deliberate schema/policy; some is UX/config.

Confirmed behavior:

- `src/web/models.py:18-20`: `ExecutionTarget` is a `StrictModel` with
  `kind: Literal["local","ssh"]` and optional `profile_id`.
  `Source.location` is `ExecutionTarget | None`; a bare string `"local"` is
  rejected with `Input should be a valid dictionary or instance of
  ExecutionTarget`. That is schema strictness, not a crash.
- `src/web/execution_plan.py:49-57`: `file_locations` must be
  `dict[str, environment]` keyed by `<node>.params.<field>` or
  `<node>.source.args.<field>`. Passing a local path is rejected with
  `file_locations must map string names to execution environments`, matching
  `docs/EXECUTION_ENVIRONMENTS.md:212-221`.
- `src/web/graph.py:72-79` and `operon/remote/server.py:215-218` reject paths
  outside configured input roots with `Input path is outside the configured server
  data roots`.

The report's data root (`D:\Operon Studio\Operon Studio\workspace`) differs from
the DSH workspace (`D:\Operon Studio\workspace`), so the root error is a
configuration mismatch. The `Permission denied` when writing
`.studio/builtin-inputs` was not reproduced.

Not a code fix:

- The strict `ExecutionTarget` and `file_locations` rules should stay; improve the
  error text to show a valid example.
- The input-root mismatch is an installation/configuration issue; document the
  expected `input_roots` and data-root layout.

## BE-08 — prepare does not ensure an SSH profile

**Type:** application/MCP behavior gap.

Evidence:

- `src/web/remote_service.py:409-445`: `prepare` resolves the profile through
  `self.catalog(graph)` and `profile(key)` and proceeds without `ensure`.
- `ensure` is a separate method at `src/web/remote_service.py:512` and is exposed
  as `operon_remote_ensure` (`operon/mcp_server.py:153-157`).

A disconnected profile therefore fails prepare until the caller explicitly ensures
it. This is confirmed.

Proposed fix (choose one):

- Call `ensure` from prepare when the profile is not connected, then continue.
- Or fail with an actionable error that names `operon_remote_ensure` and the
  profile id.

Auto-ensure has side effects (connection, host handshake) and can slow every
prepare; an explicit, actionable error is the lower-risk release change.

## BE-09 — status payload, documentation sections, timeout text, labels

**Type:** mixed application/MCP and client behavior.

Confirmed:

- `src/web/remote_service.py:104-110` returns each profile's full `info` catalog
  from `status()`, so `operon_remote_status` can be several megabytes.
- `operon/operator_docs.py:190-218` accepts only real Markdown headings plus
  `parameters` and `contracts`; `summary`, `inputs`, and `outputs` are not
  headings, so `Unknown documentation sections` is a contract mismatch.
- `src/task/manifest.py:74-81` rejects labels for unknown dimensions; that is
  correct input validation.

Not a backend bug:

- `operon/agent_views.py:23-50` returns `wait_timed_out: True` on timeout; it does
  not raise `Request timed out`. That message comes from the client/request layer.

Proposed fix:

- Add a compact/pageable `remote_status` mode (profile summary + catalog version,
  not the full catalog), keeping the full payload available explicitly.
- Accept aliases `summary`/`inputs`/`outputs` in the documentation API, or document
  the canonical section names.
- Improve the client timeout message separately; do not change the backend timeout
  contract.

## Release boundary

- These six issues need an **application** release (currently main is Studio
  4.0.5); they cannot be fixed by a library bundle. A reasonable target is
  Studio 4.0.6.
- BE-01/02/06 need the separate **Library 8.0.3** release; 4.0.6 can bundle that
  library version.
- Do not move existing tags `library-v8.0.2` or `v4.0.5`.

## Verification limits

- Remote `lihj@172.22.148.93:22` timed out; no live admission/job replay.
- The 27→21→11 canvas sequence was assessed from code, not clicked through Studio.
- BE-04 needs a coordinator integration test; a unit test alone cannot prove the
  terminal-state writeback.
