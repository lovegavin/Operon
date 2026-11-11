# Backend issues audit: Studio 4.0.4

Audit of `backend_issues.md` (BE-01..BE-09) against the exact 4.0.4 source.

Baseline: git tag `v4.0.4` = `17428b68b4853505bf816d76bb5aed2726a6e1`,
worktree `/home/gavin/Operon-404` (`operon.__version__ == "4.0.4"`). The path in the
report, `D:\Operon Studio\Operon Studio\versions\4.0.4-30b4f1538cbb`, does not
exist on this host; `D:\Operon` is a 3.0.2 checkout. Findings below are source-level
unless explicitly marked as runtime-reproduced. The remote host
`lihj@172.22.148.93` timed out, so remote job records could not be replayed.

## Summary

| ID | Verdict | Core evidence |
| --- | --- | --- |
| BE-01 | confirmed | Empty `dependencies` makes repair skip atomic operators; declared `dependency_imports` are never installed. |
| BE-02 | confirmed (declaration) | `export_results` requires `hictkpy` even for CSV/FASTA/PDB; only Hi-C export uses it. |
| BE-03 | confirmed (mechanism) | Disabling memory reserves the entire host process limit, so admission is infeasible. |
| BE-04 | confirmed (code path) | A coordinated parent is created as `queued`; no engine terminal state is copied back to `job.json`. |
| BE-05 | confirmed (mechanism) | Readiness readiness checks status only; stale `plugin_lock` entries survive graph edits. |
| BE-06 | confirmed | Interface operators publish an open 2D contract; `residue`/`cdr_index` exist only at runtime labels. |
| BE-07 | partial | Three path/schema behaviors are real; several reported errors are invalid inputs or inconsistent data roots. |
| BE-08 | confirmed | `prepare` resolves a profile but never calls `ensure`. |
| BE-09 | partial | Large `remote_status` and strict documentation section names are real; `Request timed out` is client-side. |

## BE-01 — atomic operators never repair their imported packages

`operon/dependencies.py:256-259` skips an entry when it has an explicit
`resources.environment` or when `dependencies` is empty. `interface_alanine_scan.py`,
`interface_mmgbsa_delta.py`, and `structure_interface_residue_energy.py` all declare
`dependencies: []` while listing `openmm`/`pdbfixer` in `dependency_imports`
(`interface_alanine_scan.py:156-157`). `operon/install_targets.py:232-239`
(`repair_entries`) builds targets from `descriptor["dependencies"]`, so the imports
are invisible to the installer. The reported blocked prepare follows mechanically.

Verdict: **confirmed**. Impact: these three structure operators cannot be prepared
through the normal dependency path in shared-mode environments.

## BE-02 — `export_results` has a hard Hi-C dependency

`export_results.py:125-126` lists `hictkpy>=1.4,<2` in both `dependencies` and
`dependency_imports`. The CSV/FASTA/PDB paths use only the standard library and
NumPy. `hictkpy` is imported only by the `.hic`/`.cool` branch in
`_export_contacts.py:147`. On Python 3.14 the package builds from source and fails
before a wheel is produced (CMake/Conan toolchain mismatch, missing Eigen3), which
blocks every export route during environment preparation even when no Hi-C output
is requested.

Verdict: **confirmed at the declaration level**. The exact Python 3.14 build log was
not replayed locally, but the dependency is unnecessary for the failing routes.

## BE-03 — memory disabled means reservation equal to the pool ceiling

`src/web/admission.py:220-246`: when `memory.enabled` is false, the request sets
`budget, reserved, cpus = 0, self.capacity, self.cpus`; `process_limit_bytes` then
becomes `min(reserved, ...)`, i.e. the whole host process limit. The pool's
`schedulable_bytes` is `ceiling_bytes - management_reserve_bytes`
(`operon/engine/contracts.py:259`). The unit minimum therefore exceeds the frozen
pool ceiling and `operon/engine/policy.py:166-177` marks it
`infeasible_resources`; `operon/engine/coordinator.py:639-649` records
`The unit minimum exceeds the frozen pool ceiling`. This is consistent with the
report's numbers (`203149342310` reservation, `10157467115` management reserve) and
with the same graph completing when memory is enabled.

Verdict: **confirmed by code path**; the reported admission database values were
not independently replayed because the remote coordinator was unreachable.

## BE-04 — coordinated parent jobs never receive terminal state

`src/web/service.py:664-700` creates every job as `queued` with
`queued_reason='Waiting for available host memory and CPU'`. `_submit_coordinated`
(`:728-758`) calls `engine.facade.submit(...)` and returns; it copies no status back.
`_refresh_jobs` (`:462-560`) only reconciles local owner/worker state and never reads
an engine run/attempt terminal state. `_start_coordinated` (`:1005-1030`) runs only
after a lease is committed; if admission fails first, no callback sets the parent to
`failed`. This matches the report's parent `job.json` remaining `queued` while the
child request failed and `launcher.events.jsonl` contains only `job_queued`.

Verdict: **confirmed by code path**. Runtime replay is blocked by the unreachable
remote host; the completed sibling job is not evidence against the bug.

## BE-05 — readiness does not bind to the current fingerprint

`operon/readiness.py:365-369` (`require_ready`) tests only
`readiness.get("status") != "ready"`; the stored fingerprint is never compared with
the graph being launched. `plugin_lock` is only pruned against the currently used
operator ids in `operon/readiness.py:77` and `src/web/execution.py:581`; graph
edits do not rebuild it from live nodes. `operon/plugins.py:304-317` adds pins but
never removes obsolete ones. Stale join/aggregate/export entries therefore survive a
27→21→11 node edit and can make the run fail with `environment_not_ready` after a
smaller graph prepared successfully.

Verdict: **confirmed by code mechanism**; the exact 27→21→11 UI sequence was not
replayed.

## BE-06 — interface outputs are open 2D contracts

`structure_interface_core.py:145-166` publishes
`{"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}` with no
`dims`; the `residue`/`statistic` form is created only at runtime
(`:271-300`). `structure_paratope_predict.py:153-170` is the same, and `cdr_index`
is placed in the `statistic` value column at `:248-252`, not declared as a
dimension. Static `join`/`aggregate` therefore cannot resolve `residue` or
`cdr_index`, exactly as reported.

Verdict: **confirmed**. This is a contract deficiency, not a runtime shape bug.

## BE-07 — path and execution-target strictness

`src/web/models.py:18-20` defines `ExecutionTarget` as a `StrictModel` with
`kind: Literal["local","ssh"]` and optional `profile_id`; `Source.location` is
`ExecutionTarget | None`. A string `"local"` is rejected by Pydantic with
`Input should be a valid dictionary or instance of ExecutionTarget` — the schema is
strict by design, so that part is user input, not a backend regression.

`src/web/execution_plan.py:49-57` requires `file_locations` to be
`dict[str, environment]` keyed by `<node>.params.<field>` or
`<node>.source.args.<field>`; passing a local path is invalid and is rejected with
`file_locations must map string names to execution environments`, matching
`docs/EXECUTION_ENVIRONMENTS.md:212-221`.

`src/web/graph.py:72-79` and `operon/remote/server.py:215-218` reject paths outside
the configured input roots with `Input path is outside the configured server data
roots`. The report's data root (`D:\Operon Studio\Operon Studio\workspace`) differs
from the DSH workspace (`D:\Operon Studio\workspace`), so this is a configuration
mismatch. The `Permission denied` writing `.studio/builtin-inputs` was not
reproduced.

Verdict: **partial**. The strict-schema and input-root behaviors are real; calling
them backend bugs depends on the intended UX. The reported SSH relative-path error
is consistent with the remote root check.

## BE-08 — prepare does not ensure an SSH profile

`src/web/remote_service.py:409-445`: `prepare` resolves the profile through
`self.catalog(graph)` and `profile(key)` and proceeds without `ensure`. `ensure` is a
separate method (`:512`) exposed as `operon_remote_ensure`
(`operon/mcp_server.py:153-157`). A disconnected profile therefore fails prepare
until the caller explicitly ensures it.

Verdict: **confirmed**.

## BE-09 — documentation sections, wait timeout, status size, labels

`operon/operator_docs.py:190-218` accepts only actual Markdown headings plus
`parameters` and `contracts`; `summary`, `inputs`, and `outputs` are not headings, so
`Unknown documentation sections` is a contract mismatch rather than a crash.

`operon/agent_views.py:23-50` returns `wait_timed_out: True` on timeout; it does not
raise `Request timed out`. That error originates in the client/request layer.

`src/web/remote_service.py:104-110` returns each profile's full `info` catalog from
`status()`, so `operon_remote_status` can be several megabytes — confirmed.

`src/task/manifest.py:74-81` rejects labels for unknown dimensions; the error is
input validation.

Verdict: **partial**. The large status payload and strict doc-section names are
real; the timeout error is not attributable to this backend, and the labels error is
correct validation behavior.

## Practical priority

1. BE-01 (blocks all three interface operators in shared environments).
2. BE-03 + BE-04 (queued forever with no terminal state; worst operational impact).
3. BE-02 (blocks all exports on Python 3.14 even without Hi-C).
4. BE-05 + BE-06 (stale environment and unresolvable interface contracts).
5. BE-07 + BE-08 + BE-09 (UX/contract issues, workarounds exist).

## Verification limits

- No remote replay: `lihj@172.22.148.93:22` timed out, so admission/job records and
  the reported hashes were not re-fetched.
- No Studio UI replay: the 27→21→11 graph edit was assessed from the service and
  readiness code, not clicked through.
- The 4.0.4 source is the git tag; the report's installed directory name
  (`4.0.4-30b4f1538cbb`) does not exist locally.
