# Operon 3.1.0 engine acceptance — 2026-11-08

This record replaces the earlier implementation-only handoff. Tests below ran
on the release working tree without the earlier file-stdio or mkdir shims.
Historical measurements remain in `server_engine_baseline.md`; they are not a
new benchmark of the current product.

## Release scope

The existing `legacy` scheduler remains the default. The dedicated shared pool
and workspace coordinator are explicit opt-ins. The factory library seed,
scientific implementations and frozen parameter JSON are unchanged.

Repairs in the release pass preserve ExecutionService stage orchestration in
pool mode, charge transfer buffers to the same pool, use the actual selected
interpreter for environment identity, reject unsafe cache reuse, reopen lost
subscriptions, fail closed on remote durable-claim errors, and refresh the UI
catalog after a generation change. Public desktop labels and suggested agent
commands use Operon; internal import/schema/MCP identifiers remain compatible.

## Windows evidence

Windows 11, Python 3.12.14, isolated workspace test directories:

| Suite | Result | Scope |
| --- | --- | --- |
| Frontend | 161 passed; production build passed | Existing interactions, localization and branding |
| Engine/coordinator/pool | 135 passed | State, accounting, ownership, attempts, cancellation, artifacts, bounded channels, cache and CLI |
| Product integration | 35 passed | Numeric installed-wheel workflow, stages, transfers, shared pool and cache |
| Adapter suite | 56 passed, initially 2 failed | Headless CLI, real MCP stdio, Studio, remote adapters and SDK |
| Catalog/product repair | 29 passed | Both adapter failures repaired; current generation visible after hot install |
| Final resource/remote repairs | 22 passed | Pool capacity bootstrap, resize and remote claim refusal |
| Existing regression | 127 passed, initially 1 failed, 1 skipped | Memory, storage, admission, contracts, formats and dependency handling |
| Early-error logging and real pool | 8 passed | Regression failure repaired: console exists even if interpreter inspection fails |
| Dependency file content | 1 passed | Same-version installed dependency code change alters fingerprint |

Suites overlap and must not be summed. The sole skipped storage test requires
Windows symlink creation privileges. Earlier failures and their subsequent
repairs are retained in the raw evidence; they are not silently removed. The
headless and MCP checks now pass with ordinary subprocess transport. Prior
sandbox-specific failures in the implementation handoff are not current results.

Additional release checks: 41 focused remote/coordinator tests passed, and the
pool restart test passed after explicitly waiting for the separate resource-release
phase. Native Setup checks passed (52 checks); an isolated command-line Setup
installation succeeded. The installed desktop's CLI/MCP/API backend acceptance
passed 17 checks, including actual scientific execution, explicit dependency
preparation, scopes, frozen parameters, original figures and idempotent retry.
This does not claim manual UI selection or a new test-PC double-click session.

## Real Linux and SSH evidence

The user started the existing authorized Linux instance. All work used a new
acceptance directory, synthetic arrays and two dedicated workspaces. Python
3.11.18 ran in a new venv inheriting an existing scientific test environment;
this is not a clean-machine dependency bootstrap claim.

- Initial Linux product/engine suite: **37 passed**.
- Final Linux engine/product/remote tests: **183 distinct cases passed**, combining
  per-module runs and focused repair reruns. Earlier failure logs remain archived.
- Two actual SSH clients independently handshook with workspace daemons using
  one dedicated pool. Local synthetic file upload and subsequent reuse passed.
- Both clients submitted real installed v3.7 Reader/scale workflows. Repeating
  an idempotency key reused one task. Cancelling alpha did not cancel beta.
- Closing and reconnecting SSH reused the same task. Beta completed, and its
  exported NumPy array exactly equalled the input multiplied by three.
- A separate test killed the actual pool CLI process while its scientific
  worker was running, then started a new pool process using the same state.
  The worker PID/creation identity and attempt ID were preserved, the client
  subscription reopened, retry reused the task, and its numeric output matched.
  Compute completion, artifact commit, tree exit and resource release all
  reached their confirmed states.
- Two explicit SSH bridge closes removed their bridge processes without stopping
  the shared daemon or scientific tasks. Registry refresh is single-flight even
  while the environment maintenance gate is held.
- The Linux server bundle installed into a private prefix and its standard-library
  YAML example completed all three stages from the command line.

This instance has a 1 GiB cgroup limit. An aggregate test process was OOM-killed;
module-isolated execution completed. A later combined suite left too little free
capacity for the Describe worker to start before its test timeout; the same test
passed in an isolated process (5.09 seconds). Orphaned SSH bridges were also found
and fixed; real disconnect checks confirm cleanup. These failures are retained
as evidence, not counted as successful combined runs.

The scale operator includes a synthetic delay to expose concurrency and crash
recovery. These results validate real process/SSH and numeric data paths, not
large-cohort scientific throughput. Raw evidence is archived with the release
verification. No private scientific data or credentials are included.

## Boundaries retained

- No production Reader was changed to streaming. Real Reader plus streaming
  Describe and a test-only worker adapter validate channels, not a universal
  streaming route.
- Environment maintenance uses interpreter-identity mutual exclusion, not
  immutable environment generations or rollback.
- Verified stage cache requires explicit valid contracts on every participating
  Reader/operator. Existing undeclared operators are not cached. Isolated
  dependency targets, R, external tools and dependency extras are ineligible.
- Same-version dependency file changes are tested with an installed metadata
  fixture; arbitrary third-party binary replacement is not fully validated.
- Direct pool clients require shared workspace storage. A remote pool is used
  through a co-located SSH service; a general remote artifact proxy is absent.
- Pool tokens and scheduling principals are for trusted clients under the same
  OS account, not hostile multi-tenant isolation.
- CLI process crash/restart is verified; systemd unit lifecycle, prolonged WAN
  impairment, real full-disk exhaustion and long scientific elastic-resize
  performance remain separate operational acceptance work.
- No new Windows test-PC manual Setup/shortcut claim is made in this record.
  Package/desktop checks are listed separately in release verification.

The startup capacity snapshot and emergency memory pressure handling remain
separate from task-boundary budget commands. The pool is the sole resource
allocator when enabled; an unavailable pool does not silently launch locally.
