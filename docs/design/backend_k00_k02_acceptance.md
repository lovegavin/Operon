# K00-K02 gate acceptance and follow-up

Date: 2026-11-14. Baseline `600eed6f53b6db01f7391f408ade1e950d8679b3`
(5.1.9), branch `backend/5.1.9-cluster`. This supersedes the open-work lists in
the [initial inventory](backend_k00_inventory.md) and
[initial corrective review](backend_k02_review.md); their failed evidence is
retained. No library sources, version, release artifacts or protected checkout
were changed. No commit, push, remote deployment or publication was performed.

## Gate decision

**PASS: K00-K02 are closed for the specified Windows component/product gates.**
The final grouped checks passed on Python 3.12 and 3.11, and the fixed-workload
performance comparison resolved the earlier repeatable submission regression.
Cold and warm p95/p99 improved for all measured request classes. See
[the numerical performance report](backend_control_performance.md) and
`verification/backend/gate-evidence.json` for the decision and report hashes.

K03 is now unblocked. Immutable environment generations, their production
binding/GC path and later platform gates are **not** counted as implemented or
accepted by this decision. No new environment installer or scheduler was added
while the preceding gate was open.

| Unit | Implemented behavior | Module tests | Product integration | Real E2E / scope | Remaining boundary |
|---|---|---|---|---|---|
| K00 | Selective maintenance/admission ports, bounded control, exact manifests and section 16.2 baseline | Passed, including native Setup component checks | Actual spawn guard, pool negotiation, quotas and overload cancellation | Windows real processes/sockets/scientific fixture; measured memory/queue/latency | Interactive Setup and Linux/cluster release acceptance remain K12/platform gates |
| K01 | One metadata compiler, strict schemas/identity, frozen values, complete implementation closure | Passed on 3.11/3.12 | Application and old web imports share the same implementation | Actual compilation with scientific and web imports forbidden | Relocatable binding split is K04/K05; authoring vocabulary v2 is K06 |
| K02 | Invocation ABI through existing TaskService/JobService/pool and shared Context | Passed on 3.11/3.12 | Durable replay, actual pool lease/fence, artifact validation and cancellation | Real NpyReader/PCA/plot/report branches; no-window CLI/API/MCP | Local native chain only; foreign-language and remote execution remain later gates |
| K03 | Entry conditions satisfied | Not run | Not implemented | Not accepted | Prepare immutable generations, bind attempts, prove crash/lease/GC behavior before rollout |

## K00: selective behavioral ports

| Boundary | Implemented preservation | Evidence / qualification |
|---|---|---|
| Installation lifetime | Installation-ID maintenance mutex and active event cover Setup/update/uninstall; managed-pool bootstrap/rebind and the actual worker spawn consult the same guard | `test_installation_maintenance`, `test_job_admission`; an installer crash releases the OS gate; no global Python termination |
| Removal ownership | Inspect all owned versions before deletion; Restart Manager targets locked owned files; only verified owned read-only files are cleared; distinguish explicit install from uninstall entry | Native Setup suite: 79 passed on a normal Windows token, synthetic directories/processes only; not an interactive installer acceptance |
| Overload rejection | Four bounded rejection workers; absolute drain deadline; accept thread performs no blocking socket drain | Real socket saturation/drip tests in `test_control_limits` |
| Durable admission | Atomic active-run and retained-request caps, per-principal caps, submission byte/unit limits; replay wins before rejecting capacity | Concurrent claims and 1,000 rejected submissions leave run/request/event counts bounded; no silent receipt deletion |
| Storage pressure | DB+WAL and free-space watermarks sampled outside the writer; errors deferred until after replay lookup | Slow-disk/read concurrency and replay-during-pressure tests; watermarks are not hard scientific-output filesystem quotas |
| Request fairness | Authenticated workspace/session identity, token bucket and concurrency cap; bounded identity tables with separate lifecycle allowance | Invented principal and extra sessions do not multiply allowance |
| Cancellation under overload | Separate authenticated 4-handler / 64-KiB lifecycle listener; ping/status/cancel/detach only; advertised capability and client negotiation | Main listener filled with 32 silent clients while real pool status, cancellation and detach succeed; no bulk fallback when lifecycle endpoint fails |
| Author 5.1.9 fixes | UTF-8 probes, deep Windows DLL/module/resource paths, installing state, commit/rollback, library resource/environment manifests | Focused Python 3.11/3.12 regressions; no replacement of author scientific implementations |

Default control limits are 32 main handlers, 4 rejection workers, and 2 concurrent
planning dispatches. `OPERON_CONTROL_PLANNING_HANDLERS` can tune the latter in
both the host pool and SSH control configuration. Waiting planning calls still
consume bounded handler/decoded-byte capacity and an absolute deadline. These
are control-service limits, not scientific-worker CPU or memory allocations.

The older local standalone-export patch is inventoried but deliberately not
whole-file copied; its behavior belongs to K05. The protected old dirty checkout
was not reset, stashed, cleaned or rewritten.

## K01: one compiler, with inward dependencies

`operon.planning.graph_compiler` is now the single graph compiler. Pure graph
models, contracts, parameter freezing, source references and route expansion
live beside it. The old `src.web` modules are compatibility aliases to those
same modules; the route-library persistence service stays in the web adapter.
`WorkflowCompiler` and `Application.compile_plan` use identical semantics.

- Strict versioned contracts reject unknown fields/scalar coercion; nested
  parameter values are immutable and copies are revalidated.
- Defaults freeze once. Explicit null, false and zero are not replaced by a
  later library declaration. Independent workflow parameter JSON is preserved.
- Nested routes, automatic Readers, generated converters and script code all
  contribute to the implementation/dependency closure. Ambiguous conversion,
  duplicate input ports, malformed containers and oversized expansion fail
  explicitly before expensive work.
- A fresh subprocess compiles a real graph while rejecting imports of the web
  layer, scientific libraries and operator/Reader implementations. Static
  declaration access does not import the scientific code.
- Canonical hash vectors and generated schemas are checked. Implementation
  identity excludes declaration/default-only audit changes and retains code,
  package version, resource digest and SDK ABI when supplied.
- Relative source bindings retain their subdirectories. External sources use
  separate node-specific root references even when their basenames coincide;
  the local compatibility payload provides the actual paths until K05 supplies
  explicit portable bindings.
- Successful parameter-schema validation is reused by content in a bounded
  128-entry cache (at most 64 KiB ASCII JSON per key). Parameter values are
  still validated each time; mutable defaults are copied, altered declarations
  are checked again, and oversized schemas are checked without retention.
- Existing plugin pins are retained and checked, including known bundled-code
  migration and installed-wheel generations. Unknown implementations are not
  made available by clearing `plugin_lock`.

The K02 compatibility RunPlan still hash-binds its **entire executable payload**,
including absolute paths and UI fields retained by that payload. Workflow
identity is presentation-independent, but this compatibility RunPlan is not yet
a relocatable portable identity. K04/K05 must split machine bindings explicitly;
removing executable payload from the hash is not an acceptable shortcut.

## K02: execution authority and scientific parity

The invocation runner requires `Application`, recompiles and verifies the plan,
then submits through the existing durable `TaskService`/`JobService` or shared
pool. It does not start a process directly or fall back to a second allocator.
Both worker entry points share frozen-plugin bootstrap and the existing Context.

Real `NpyReader -> PCA -> {scatter, describe}` runs compare explained variance,
shape, dimension/axis labels, info, figure metadata/PNG dimensions, memory report,
native outputs and logs. A real local TCP pool owns the attempt/fence/lease;
replaying `run-plan:<id>` returns the same job. A real script worker is cancelled
and its owned process tree is confirmed stopped. Input data remain path
references across the invocation boundary.

The collector only verifies the worker-created SHA256 inventory. Missing or
modified outputs, path escape, an unaccepted exit, mismatched plan contents,
unavailable task authority and unconfirmed tree stop cannot become success.
Unconfirmed termination retains recovery state and resource ownership.

This gate covers one local native chain unit, including branches inside the
existing task engine. Multi-unit foreign-language handoff, remote RunPlans and
portable runtimes are later gates, not silently approximated here.

## Evidence and reproducibility

Evidence is under `verification/backend/`. Old failed XML files are historical;
repeated test runs must not be added together as unique coverage. Final source
hash manifests identify the dirty checkout, not merely its unchanged HEAD.

`verification/backend/run_gate_checks.ps1` runs the final grouped acceptance:
Python 3.12 product/regression tests, Python 3.11 native/contract checks, exact
source/runtime manifests, then the same isolated baseline/candidate performance
workloads. Interpreter and baseline paths are explicit arguments; it does not
alter the machine's configured interpreter or install dependencies. The final
batch follows development freeze; earlier failed experiments remain recorded.

| Final selected check | Result | Evidence |
|---|---|---|
| Python 3.12.14 grouped regression, real native workers, TCP pool, no-window CLI/API/MCP | 129 passed, 0 failed/errors/skipped | `gate-batch-py312.xml` |
| Python 3.11.15 contracts, control, admission, real native invocation and environment manifests | 66 passed, 0 failed/errors/skipped | `gate-batch-py311.xml` |
| Windows native Setup maintenance/ownership regression (unchanged after this run) | 79 passed | `native-setup-final.txt` |
| Additional retained 3.12 author-fix/maintenance checks | 76 passed at that checkpoint | `gate-final.xml`; overlaps with the final selected check, not additive coverage |
| Additional retained 3.11 DLL/resource/UTF-8 checks | 13 passed at that checkpoint | `python311-runtime.xml` |
| Exact final Python/package/source inventories | 1,065 source/test/build files hashed per runtime, plus configuration/schema hashes and installed-distribution metadata | `k00-runtime-final-py311.json`, `k00-runtime-final-py312.json` |

Both final pytest batches emit the same FastAPI/Starlette test-client deprecation
warning; it is not a runtime failure or a skipped test. No dependency update was
performed merely to silence it. The two interpreter rows are separate executions,
not 195 distinct test definitions.

All tests use synthetic data. The Python 3.11 scientific acceptance uses a new
isolated test venv under `.scratch`, with the current long-path import hook;
the existing management runtime remains untouched. Optional R and UMAP are
not prerequisites of the selected native K00-K02 fixture. The expanded domain
regression recorded an unavailable UMAP example and a missing R executable;
that is not evidence that those operators work. A separate script-package
promotion failure exposed a genuine host-version bug (`<4` on 5.1.9), now fixed
and rerun with a real built/installed provider.

The environment-manifest suite formerly required an absent untracked release
archive. Its new deterministic synthetic wheel fixtures verify composition,
integrity and resource metadata without modifying `library/seed`. They do not
claim to run protein-design software or PDBFixer's scientific algorithm.

No Linux/SSH/Slurm, multi-host failover, real R/native boundary, desktop GUI,
Setup packaging, relocation or publication acceptance is included. The local
scientific/transport tests and native Setup component tests are labelled as
such; they are not substitutes for K04-K12 platform gates.
