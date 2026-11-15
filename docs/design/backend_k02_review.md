# K00-K02 initial implementation review (historical)

This is the initial corrective review, retained as failure and decision history.
Its "Remaining work" list describes that checkpoint, not the current checkout.
See [K00-K02 gate acceptance](backend_k00_k02_acceptance.md) and
[the performance comparison](backend_control_performance.md) for the follow-up
ports, compiler convergence, final evidence and advancement decision.

Date: 2026-11-14. Baseline: `600eed6f53b6db01f7391f408ade1e950d8679b3`
(5.1.9). Branch: `backend/5.1.9-cluster`. All changes remain local and
uncommitted. No version, library seed, release artifact or protected checkout
was changed. This review does **not** authorize advancement to K03.

## Gate decision

The submitted implementation did not satisfy the K02 execution-authority
invariant. Its `InvocationRunner` constructed `ExecutionContext(lease=None)`
and called `ProcessExecutor` directly. Reusing a supervisor is not equivalent
to passing through host admission, environment exclusion, durable submission
and pool resource ownership. The submitted inventory's statement that the
existing JobService remained authoritative was therefore inaccurate.

That bypass is repaired. Local native RunPlan execution now submits through
the existing `TaskService` and `JobService` (or its configured shared pool).
K00 remains incomplete, and the metadata-only compiler still has a narrower
scope than the application compiler. Consequently **K00-K02 as a combined
gate remains open**; this is not a full backend or export acceptance.

## Corrections made

| Boundary | Original defect | Correction and evidence |
|---|---|---|
| Resource authority | Direct process launch without a lease | Runner never launches a process; unbound execution fails with `admission_required`. Pool/service errors do not trigger a local fallback. Real TCP pool + scientific worker test verifies the pool owns the attempt and releases its lease. |
| Durable submissions | Runner-local attempt naming was not product-level deduplication | `run-plan:<run_id>` is submitted through the existing durable request path. Repeating the same request returns the same job and attempt. |
| Plan identity | Executed `unit.payload` was removed from the hash | Executable payload is included; submission also recompiles the graph against the selected catalog and rejects a rehashed but inconsistent payload. `plan_identity` and `RunPlan.compute_id` use one implementation. |
| Frozen values | `strict=False` coerced scalar types; nested dictionaries remained writable | Strict scalar validation, JSON-compatible immutable nested containers and validated copies. The legacy boundary converts immutable sequences back to JSON lists, including script dependencies. |
| Pins and implementation closure | Graph projection lost `plugin_lock`; nested route operators were absent | Preserve locks during projection, resolve the graph-selected catalog, recursively collect route implementations, and check implementation identity again at the execution host before preparing the worker. |
| Worker bootstrap | New worker omitted the normal frozen plugin activation | Both worker entry points use `operon.worker.execute_task`, preserving target activation, plugin locks, independent parameters, RunLog bootstrap failures, Context finalization and exchange outputs. |
| Output acceptance | Collector could reconstruct success and overwrite evidence | Worker writes a file/size/SHA256 manifest after finalization. Collector is read-only and rejects missing/changed inventory, escaped paths, failed summaries and unconfirmed process exit. Hashing uses bounded reads. |
| Cancellation | Cancel/timeout could imply termination without proof | Cancellation goes through the task service. Unconfirmed stop returns `recovery_required`; the runner never releases leases. Process exit, artifact commit and resource release remain distinct. |
| Attempt identity | Runner manufactured its own attempt/fence | Managed invocations receive the existing coordinator attempt and its persisted fence; legacy execution records fence zero. |
| Path containment | Attempt/output names could traverse outside their roots | Validate run IDs, storage-relative paths and invocation manifest paths; check resolved worker paths before creating directories. |

The new ABI is selected by an internal `runtime.native_invocation` marker in
the prepared graph. JobService still selects the interpreter from the frozen
plugin lock and owns environment leases, thread limits, memory allocation,
process startup and the watcher. The ordinary worker path is unchanged when
the marker is absent. No new allocator, scheduler or dependency installer was
introduced.

## Verification

Evidence is in `verification/backend/`:

- `k00-k02-review-regression.xml`: focused contracts, invocation, admission,
  coordinator, unified pool entry, workflow/catalog and upstream environment
  commit/manifest regressions: **78 passed / 5 failed**. The new contract and
  invocation tests account for **22 passed / 0 failed** (13 + 9).
  `baseline-extra.xml` reproduces the same five failures in the untouched
  baseline: one artifact path-rebasing `KeyError` in the independent-workers
  test and four missing `build/lib512/*.operon-library.zip` fixtures. No
  library fixture was synthesized or substituted to turn those tests green.
- `k02-pool-review.xml`: real local TCP shared-pool execution of
  `NpyReader -> pca -> {scatter, describe}`, persistent attempt/fence, release
  and repeated-request reuse. No readiness or scientific-worker mock.
- `headless-baseline.xml` and `headless-review.xml`: same interpreter and
  tests against an untouched archive of the pinned baseline and this worktree.
  **Both returned 5 passed / 4 failed.** The failing assertions are the same:
  empty `plugin_lock.describe`, absent `bundled_updates`, remote preparation
  pin expectation and CLI autostart's pin expectation. This establishes no
  new failure in that comparison, not a passing headless acceptance or proof
  that production pin handling is correct.
- `python311-review.json`: CPython 3.11.15 import, strict scalar and canonical
  serialization smoke checks. This is not a full 3.11 scientific execution
  acceptance. Main execution tests use CPython 3.12.14 on Windows.
- `k02-review-final.xml`: final invocation-only rerun after tightening native
  worker entry/path validation and traceback preservation.
- `review-summary.json`: test summaries, reproduced baseline failure IDs and
  SHA256 hashes of the changed source/test/document files (including untracked
  new modules); the source revision alone does not identify a dirty worktree.

The original numerical parity fixture and real script cancellation are retained.
Additional fault cases reject a modified executable payload (including after
rehashing), corrupt/missing outputs, an unavailable task authority and a stop
without process-tree evidence. The original input stays a path reference;
crossing the ABI does not copy the full input dataset.

An initial shared-pool test during this repair exposed an incorrect attempt
fence lookup. That local edit was corrected to read the persisted attempt
outside the job lock; the subsequent real pool test passed. Failed intermediate
runs are not acceptance evidence.

## Remaining work before advancing

1. **Port the protected local K00 fixes by behavior.** The new tree has no
   `operon/installation_maintenance.py` or `operon/engine/admission_limits.py`.
   Its `ControlLoop` still performs rejection I/O on the submitting/accept
   thread. The old checkout's bounded rejection workers/absolute drain
   deadline, queue/receipt/disk admission policies, principal request limiter
   and Setup/managed-pool maintenance guard need explicit ports and their
   regressions. Passing existing admission tests does not cover these missing
   changes. Do not replace whole files from the old namespace.
2. **Converge compilation semantics.** `WorkflowCompiler()` still contains a
   limited metadata compiler while `Application.compile_plan()` injects the
   existing full compiler. Converter ambiguity, auto-reader resolution,
   dependencies/resources of generated converters and scripts, nested route
   expansion limits and complete frozen-value projection need parity tests.
   The application path rejects inconsistent plans rather than executing a
   plan produced by incompatible semantics.
3. **Separate semantic content from machine bindings before portability.**
   For K02 integrity, the compatibility payload is hash-bound in full. Its
   absolute execution paths and presentation metadata can therefore change a
   plan ID. Do not claim relocatable RunPlan identity or multi-host reuse yet.
   K04/K05 must extract explicit storage/environment binding records rather
   than excluding executable payload from identity again.
4. **Record the required performance baseline.** Contract section 16.2's
   mixed-client control latency, writer wait/hold, queue growth and memory
   measurements have not been performed in this review.
5. **Close broader platform gates separately.** No Linux/SSH/Slurm,
   multi-language or conflicting-environment export, UI/Setup, package
   relocation or release test was performed. No paid server was started.

K02 currently executes one local native chain unit through a local or explicitly
configured shared-filesystem pool. Remote and staged RunPlans fail explicitly;
normal existing application execution remains available for those workflows.
The observer receipt is not a new scheduler journal or cross-host authority.
Environment generations/GC (K03), foreign-language adapters (K04) and portable
packages (K05) remain unimplemented.
