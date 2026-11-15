# K00 baseline inventory and preservation record

Date: 2026-11-14. This records the protected baseline and the initial checkpoint.
See [K00-K02 gate acceptance](backend_k00_k02_acceptance.md) for current status,
selective port coverage and final evidence; the original review and checkpoint
below are retained as history, not an outstanding-work list.

## Protected integration checkout

| Item | Value |
|---|---|
| Existing dirty checkout | `<project>/worktrees/BioPipe-result-viewers`, branch `fix/3.0.1-installation` |
| Existing dirty checkout HEAD | `0f2c87cd` (dirty local maintenance/admission/export patches; preserved in place) |
| Existing dirty checkout action | Not reset, cleaned, stashed or replaced |
| New integration checkout | `<project>/worktrees/Operon-backend-5.1.9` |
| New branch | `backend/5.1.9-cluster` |
| Fixed baseline | `600eed6f53b6db01f7391f408ade1e950d8679b3` (application 5.1.9) |
| Library source | Baseline `library/seed`; not rewritten, re-versioned or merged from another branch |
| Baseline manifest | [`verification/backend/k00-runtime.json`](../../verification/backend/k00-runtime.json) |
| 5.1.9 author fixes already present | UTF-8 probe decoding (`613bd696`), Windows-safe environment commit (`fd621422`), PDBFixer resource manifest/vendored files (`9592eab9`, `600eed6f`) |

The baseline is pinned by commit and is not tracking moving `main`. Later upstream
commits are not silently merged.

## Runtime and dependency inventory

`scripts/backend_runtime_manifest.py` records:

- exact worktree path, branch, HEAD and dirty flag;
- CPython/platform/executable;
- installed versions of pydantic, FastAPI, Uvicorn, Paramiko, psycopg, NumPy,
  PyYAML, psutil, jsonschema, packaging, pytest and the optional scientific
  stack;
- the planning import-boundary list and the test that enforces it.

Observed at inventory time: CPython 3.12.14 (source compatibility target; the
release management runtime remains CPython 3.11), pydantic 2.14.0, FastAPI
0.143.0, Paramiko 4.0.0, NumPy 2.5.4, PyYAML 6.0.3. psycopg is not installed in
this management environment because it is a cluster-service extra.

## Local maintenance/admission preservation

The older 3.1.6 checkout contains local Setup maintenance, admission-limit,
installation-maintenance and native-export patches. They were **not**
whole-file-copied into the 5.1.9 tree. Existing ownership modules and passing
baseline tests do not establish preservation of those patches. The initial
review identified missing ports of bounded rejection workers, queue/principal
admission limits and the installation maintenance guard. Those behavioral ports
are now present; their scope and evidence are recorded in the gate acceptance
document. The following was the initial baseline suite:

- `tests/test_control_limits.py`
- `tests/test_engine_policy.py`
- `tests/test_job_admission.py`
- `tests/test_engine_control.py` (if present in the selected baseline)

Any missing old-version test is a porting task, not silently declared passed.
No operator/library code or saved parameter values were changed in this unit.

## Original progress table (superseded)

| Unit | Implemented behavior | Module tests | Product integration | Real E2E | Remaining blockers |
|---|---|---|---|---|---|
| K00 | Protected 5.1.9 worktree; runtime/dependency manifest; import boundary; baseline identity | manifest script | baseline application starts and catalogs library | — | Old 3.1.6 maintenance/export patches are inventoried, not wholesale-merged; full 16.2 performance baseline remains |
| K01 | Strict WorkflowSpec/RunPlan/Invocation/environment/storage contracts; canonical JSON and identities; native metadata compiler; legacy graph compiler adapter; deterministic route expansion through existing compiler; generated schemas | `tests/test_run_plan_contract.py` | `Application.compile_plan` | Native fixture compiles without operator imports | Old/new authoring-vocabulary normalizer is K06; pure compiler currently requires application adapter for route/script nodes |
| K02 | Invocation ABI through durable TaskService/JobService; common frozen-plugin bootstrap; Context bridge; cancellation and read-only output validation | `tests/test_invocation_context.py` | Direct launch bypass repaired; existing JobService/shared pool is now authoritative | Real NpyReader→PCA→scatter+describe parity, script cancellation and local TCP shared-pool lease/replay | Local native chain only; no foreign-language, remote or portable execution acceptance |

## Evidence commands

```text
python scripts/backend_runtime_manifest.py
python -m pytest tests/test_run_plan_contract.py -q
python -m pytest tests/test_invocation_context.py -q
python -m pytest tests/test_control_limits.py tests/test_engine_policy.py \
  tests/test_job_admission.py -q
```

The generated schemas live in `operon/contracts/schemas/`; `PUBLIC_MODELS` and
`schemas()` are the source of truth.


## Original reported checkpoint (superseded by corrective review)

| Check | Result |
|---|---|
| `tests/test_run_plan_contract.py` | 10 passed |
| `tests/test_invocation_context.py` | 3 passed (real branched parity, output rejection, real script cancellation) |
| K00 focused maintenance/admission suites (`test_control_limits`, `test_engine_policy`, `test_job_admission`) | 27 passed |
| `tests/test_workflow_spec_v3.py`, `test_engine_catalog_generation.py` | passed |
| CPython 3.11.15 import/compile compatibility for `operon.contracts`, `operon.planning`, `operon.execution` | passed |
| `tests/test_headless_application.py` | Original reported count was 23 passed / 4 failed. Fresh isolated baseline and revised-tree runs each have 5 passed / 4 failed; see the two XML reports and corrective review. |

The K02 parity fixture is a real native `NpyReader -> pca -> {scatter, describe}`
route. It compares PCA explained variance, describe shape/dims/info/labels, figure
metadata/PNG dimensions, managed-memory report and log presence with a normal
`Application.jobs` execution. The cancellation fixture launches a real Python
script step through TaskService/JobService and verifies the attempt settles as
cancelled without an owned process left behind. The former direct executor
launch was rejected during review and removed.
