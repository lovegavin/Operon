# Five-layer test standard

Status: **normative**. This document defines the minimum verification that a
library release must carry. It applies to operator changes, Reader changes,
route changes, contract changes and release packaging. It does not replace the
per-operator audit in `docs/verification/operator-audit-<version>.md`; the audit
measures catalog coverage, while this standard measures release safety.

The five layers are independent. A release is not verified because a later
layer passed while an earlier layer failed. Every layer reports one of:

- `PASS` — every required item ran and met its criterion.
- `FAIL` — at least one required item ran and did not meet its criterion.
- `SKIP` — the item is not applicable or its precondition is unavailable; the
  reason, owner and scope must be recorded. `SKIP` is never counted as `PASS`.
- `BLOCKED` — the item could not be attempted because an external dependency
  is unavailable. `BLOCKED` is a release decision, not a pass.

## 1. Evidence rules

1. Evidence is tied to one commit and one library version. A test run on an
   uncommitted tree is not release evidence.
2. Every command in the evidence file must be copy-paste runnable, with the
   Python interpreter, working directory and environment variables recorded.
3. Raw logs are retained. Summaries are derived from logs, never hand-written
   from memory.
4. A numeric result needs a tolerance and an oracle. "Looks plausible" is not
   a criterion. Default tolerances are `rtol=1e-6`, `atol=1e-9` for float64 and
   `rtol=1e-4`, `atol=1e-6` for float32.
5. Synthetic inputs are allowed only when labelled `mode=synthetic`; they must
   not be presented as biological conclusions. A synthetic route run proves
   wiring and contract behaviour, not biological validity.
6. The same implementation must not be used as both the code under test and its
   only oracle. Each numerical oracle layer needs at least two independent
   implementations when the result is used in a release claim.
7. No path outside the repository is required for a reproducible check unless
   the check is explicitly marked `SKIP_EXTERNAL` with the missing precondition.

## 2. Layer model

| Layer | Question | Typical owner | Release blocking |
| --- | --- | --- | --- |
| L1 contract and manifest | Are declarations, contracts, routes, docs and hashes internally consistent? | library maintainer | yes |
| L2 unit and oracle | Do the changed units behave correctly against an independent oracle? | domain owner | yes |
| L3 route runtime | Does each changed route run end to end from files through its declared Readers? | route owner | yes |
| L4 resource and regression | Does the full suite, memory path and installation path still work? | release manager | yes |
| L5 adapter and application integration | Can the target application install the bundle and import/run its routes? | integration owner | yes for a claimed compatible release |

L1–L3 are per-change. L4 and L5 are per-release.

## 3. L1 — contract, manifest and static consistency

Purpose: catch declaration drift before any execution and confirm that the
shipped contract definitions still compile. This layer is cheap and must run on
every commit that touches `library/seed`.

The per-operator audit reports static declaration checks as L0 and contract
behaviour as L1. This release standard folds both into L1 because a release
preflight must run them together. Cite this document for release testing and
the audit document for catalog coverage; the two use different granularity.

Required checks:

1. Registry consistency:
   `python -m operon registry check --json` reports `errors: 0`.
2. Descriptor inventory: operator and Reader counts match the release note; the
   package list is exactly the intended set; no operator appears twice.
3. Documentation index: `python scripts/build_operator_docs.py --check` reports
   zero changed entries and zero errors.
4. Portability: `python scripts/audit_portability.py` reports zero findings.
5. Route definitions compile against the target application. For Studio 4.0.0
   this means loading the shipped catalog, replacing each source path with a
   virtual path, and calling the application's `compile_graph` for every
   built-in route. The expected result is `N/N` compiled and zero failures.
6. Implementation hashes: for every provider, the descriptor `code_sha` equals
   the application's `code_hash(entry_point, library_root)`. Checking only one
   provider is insufficient because a stale manifest can affect all providers.
7. Archive hygiene: the bundle contains no file from the retired `biopipe`
   namespace, and `library.json` declares `format: operon.library`, the expected
   version and the expected `minimum_application`.
8. `git diff --check` is clean and the worktree is clean at the recorded commit.

Pass criterion: all eight checks pass. A route compile failure is `FAIL`, not
`SKIP`: the route is shipped and the application will try to register it.

## 4. L2 — unit and oracle

Purpose: prove that changed code computes the intended values, including edge
cases and contract rejection.

Required checks:

1. Changed operators and Readers have focused unit tests. For each changed file,
   the test file must be named in the evidence.
2. Contract tests cover the positive path and at least one deliberate contract
   violation. A new optional `info` field needs a test proving that a Form
   without it is accepted, and a Form with an invalid value is rejected.
3. Numerical tests compare against an independent implementation, not against
   the operator's own previous output. Record the oracle name, version, input
   checksum, output and tolerance.
4. Route-graph execution with synthetic Forms may be used here for wiring, but
   it does not replace L3 (file Readers and real paths).
5. `tests/test_library_release.py` and the release archive tests must pass.

Pass criterion: zero failures in the focused set; every skip has a concrete
reason. A test that cannot run because an optional dependency is absent is
`SKIP_DEP`; it does not fail the layer, but the affected operator cannot claim a
numerical oracle in that environment.

## 5. L3 — route runtime

Purpose: exercise the same path a user exercises: a route directory, files on
disk, declared Readers, `parameters.json`, and the real runner.

Required checks, for every changed route:

1. Create a route directory with `task.yaml`, `parameters.json` and `input/`.
   `parameters.json` steps must match `task.yaml` in name, order and inputs.
2. Run `scripts/run.py <route> --check` and require a clean check.
3. Run `scripts/run.py <route>` and require exit code 0 and the runner's normal
   completion marker.
4. Record elapsed time, per-step status, output artifact names and sizes, figure
   counts, and at least one numeric value per branch.
5. Prove that the intended Reader was used. This is the point of L3: an
   in-memory test can pass while the file extension still selects the wrong
   Reader. Record the selected Reader class or a log line that names it.
6. Verify that exports/figures are inside the run directory and that no output
   escapes to the repository root or an arbitrary absolute path.
7. For a route whose inputs are not redistributable, `SKIP_DATA` is allowed only
   when the missing file, its expected schema and the owner are recorded. The
   route then has no L3 runtime evidence and cannot be claimed as run.

Pass criterion: all changed routes `PASS`. One failing route fails L3 for the
release even if the route is unrelated to the headline change, because shipped
routes are part of the catalog.

## 6. L4 — resource and regression

Purpose: catch cross-cutting regressions and release-wrapper regressions.

Required checks:

1. Full `pytest -q` on the release commit. Zero failed. Every skip is listed
   with its reason; a large skip count must be summarized by category.
2. If the change touches memory, streaming, spill or transfer, run the
   spill/quota/determinism checks and record the artifact hashes with and
   without spill.
3. Build the release bundle with the same command CI uses. Verify
   `passed: true`, operator/Reader counts, `idempotent_install` and
   `worker_streaming`.
4. Re-run L1 after the build, because packaging can rewrite the manifest.
5. Confirm `git diff --check` and that no generated file was left outside the
   declared output directories.

Pass criterion: full suite zero failures, release verification true, and no
unexplained skip.

## 7. L5 — adapter and application integration

Purpose: prove the artifact works where users install it, not only in the
source tree.

Required checks:

1. Install the bundle into a clean profile of the minimum supported application
   and of the target application. Record the application version and exit code.
2. Import the Routes zip. Require every bundle to contain exactly
   `graph.json`, `parameters.json` and `execution.json`, and every route to
   register. Record `registered/total`.
3. Open at least one route and run it, or execute the same route through the
   application CLI/HTTP/MCP adapter. Compare artifact names and hashes with the
   L3 run where the inputs are identical.
4. For a Windows compatibility claim, repeat the install and one route run on
   Windows. A Linux-only run cannot support a Windows claim.
5. Studio UI automation is optional; when it is not run, say so explicitly and
   do not claim UI verification.

Pass criterion: install and route import pass on every claimed application
version. Adapter parity is required only for adapters named in the release note.

## 8. Change impact matrix

| Change | L1 | L2 | L3 | L4 | L5 |
| --- | --- | --- | --- | --- | --- |
| Operator source only | required | required | affected routes | full suite | install + one route |
| Operator contract / `info` | required | required | affected routes | full suite | install + route import |
| Reader source or selection | required | required | affected routes | full suite | install + route import |
| Route `task.yaml` | required | not required | required | full suite | route import |
| Manifest / packaging | required | archive tests | not required | required | required |
| Version / release metadata only | required | not required | not required | full suite | required |
| Documentation only | docs check | not required | not required | not required | not required |

"Affected routes" means every route that references the changed operator,
Reader or contract, not only the route named in the release note.

## 9. Release gate

A release may be tagged only when:

1. L1 and L4 are `PASS`.
2. L2 is `PASS` for every changed operator/Reader.
3. L3 is `PASS` for every changed route.
4. L5 is `PASS` for every application version named in the release note.
5. Any `SKIP` is listed in the release note with reason, owner and impact.
6. The evidence file matches the tagged commit.

A hotfix may shorten the schedule, not the evidence. If a layer cannot run, the
release note says which layer is missing and the release is marked
`verification incomplete`; it is not described as fully tested.

## 10. Evidence file

Store one JSON file per release, for example
`verification/five-layer-<version>.json`, plus raw logs under the same directory.

```json
{
  "library_version": "8.0.1",
  "commit": "62a0f5a8",
  "application": "3.1.9",
  "target_application": "4.0.0",
  "generated_at": "2026-11-11T00:00:00+08:00",
  "layers": {
    "L1": {"status": "PASS", "checks": []},
    "L2": {"status": "PASS", "summary": {"passed": 0, "failed": 0, "skipped": 0}},
    "L3": {"status": "PASS", "routes": []},
    "L4": {"status": "PASS", "pytest": {"passed": 0, "failed": 0, "skipped": 0}},
    "L5": {"status": "SKIP", "reason": "Studio UI not automated"}
  },
  "release_blocking": []
}
```

Each check has `name`, `command`, `status`, `key_output` and `error`. Logs are
referenced by path relative to the evidence directory.

## Appendix A — 8.0.1 inventory

8.0.1 changes relative to 8.0.0:

| File | Change |
| --- | --- |
| `src/task/step/steps/cox_regression.py` | removed static `labels_axis` field requirement |
| `src/task/step/steps/kaplan_meier.py` | removed static `labels_axis` field requirement |
| `src/task/step/steps/logrank_test.py` | removed static `labels_axis` field requirement |
| `src/task/step/steps/missing.py` | output declares `missing_code` (required) and `ploidy`/`representation` (optional) |
| `routes/gwas/task.yaml` | explicit `VcfReader` / `CsvReader` |
| `routes/survival/task.yaml` | explicit `TsvReader` |
| `routes/proteomics_de/task.yaml` | explicit `CsvReader` |
| `operon/builtin_packages.json` | `code_sha` regenerated from the source tree |
| `library/release.json` | version 8.0.1 |
| `library/pyproject.toml` | version 8.0.1 |

Evidence before this test round: 4.0.0 `compile_graph` 79/79; bundle
`verify_library_release.py` `passed: true`; bundle install into a 4.0.0 profile
exit 0; `tests/test_library_release.py` 9 passed; GitHub release 14 assets with
`SHA256SUMS` 13/13.

### 8.0.1 test round

Tested at commit `62a0f5a8` (tag `library-v8.0.1`).

| Layer | Result | Evidence |
| --- | --- | --- |
| L1 | PASS — 7/7 checks; 79/79 routes compile; 1171 descriptors; registry errors 0 | `verification/five-layer-8.0.1/L1_static.json` |
| L2 | PASS — 45 passed, 0 failed, 0 skipped | `L2_targeted.json`, `L2_pytest.log` |
| L3 | PASS — 3/3 routes run from files (gwas, survival, proteomics_de) | `L3_routes.json`, `L3_*.log` |
| L4 | PASS — 3722 passed, 209 skipped, 0 failed in 2567.29 s | `L4_pytest.log` |
| L5 | PASS — install on 3.1.9 and 4.0.0; 79/79 route bundles valid; Studio UI SKIP | `L5_routes.json` |

The L4 run used a local, untracked `frontend/dist` symlink to the Studio 4.0.0
frontend because this library worktree does not carry frontend build output.
Without it, six desktop/portability tests fail on a missing `frontend/dist`;
with it they pass 16/16. The 209 skips are pre-existing optional-dependency and
feature skips; they are not failures. Studio UI automation was not run, so no UI
verification is claimed.

Consolidated evidence: `verification/five-layer-8.0.1/evidence.json`.

## Appendix B — command template

```bash
cd /path/to/Operon-worktree
export PY=/path/to/python
$PY -m operon registry check --json
$PY scripts/build_operator_docs.py --check
$PY scripts/audit_portability.py
$PY -m pytest -q tests/test_upstream_operators.py tests/test_builtin_routes.py \
  tests/test_contracts.py tests/test_library_release.py
$PY scripts/run.py /tmp/routes/gwas --check
$PY scripts/run.py /tmp/routes/gwas
$PY -m pytest -q
$PY scripts/release_library.py --tag library-v<version> --output /tmp/build-<version>
$PY scripts/verify_library_release.py --bundle /tmp/build-<version>/Operon-Library-v<version>-Linux.operon-library.zip
```
