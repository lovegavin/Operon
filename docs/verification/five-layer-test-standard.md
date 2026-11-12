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
| L5 release-artifact installation | Can the frozen bundle install into a clean target profile, prepare its environments and run a changed route? | integration owner | yes for every claimed application/OS |

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
9. Dependency declaration audit: every operator with `dependency_imports` must
   also declare non-empty `dependencies`, or a named `resources.environment`
   that owns those imports. An empty `dependencies` list with no environment is
   a `FAIL`, even when the import happens to exist in the base interpreter.
   Environment-managed operators are not required to duplicate the environment
   file's pins in `dependencies`, but the environment name must be present in
   the descriptor. Run the audit through `tests/test_contract_compositions.py`.

Pass criterion: all nine checks pass. A route compile failure is `FAIL`, not
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

### 4.1 Composition matrix (normative)

A contract is not verified by a single positive case. Every declared composition
edge must be tested, because `join` and `aggregate` consume different parts of
the same schema:

- For every numeric 2D output and every declared dimension, `join`'s bound
  requirement (`dims: [<that dimension>]`) must return exactly `compatible`.
  `unknown` does not pass; a genuinely dynamic dimension must be excluded only
  by a named allowlist entry with a reason. The dimension must also survive one
  real `JoinStep.run` call with two synthetic Forms, so a schema that says
  `compatible` while row labels or encoders fail is still a failure.
- For every label on the second dimension, `aggregate`'s bound requirement
  (`labels_axis: [{axis: 1, values: [<label>]}]`) must return exactly
  `compatible`.
- Every label must also survive one real `AggregateStep.run` call with two
  synthetic Forms. A schema that says `compatible` while the encoder rejects the
  value is still a failure.
- Any numeric 2D output whose second dimension is `statistic` or `score` must
  declare that dimension's labels. A missing `labels` entry is a `FAIL`; code
  that only sets labels at runtime is not sufficient, because the static
  interface cannot prove the composition.
- The matrix is generated from the shipped `STEPS` catalog, not from a
  hand-written operator list. Adding an operator or a label extends the test
  automatically.

The executable form is `tests/test_contract_compositions.py`. Three PRS
operators (`prs_af_filter`, `prs_harmonize`, `prs_ld_clump`) are allowlisted
because their statistic column is named by the runtime `weight_label`
parameter and cannot be fixed in the static schema. Data-defined matrices
(`paga_connectivity`, `pseudotime_dpt`, `trajectory_gene_trends`) are outside
the statistic/score rule because neither axis carries a fixed column label.
Every allowlist entry must name the operator, the dimension and the reason, and
must be re-reviewed whenever the output changes.

### 4.2 Dependency audit (normative)

`dependency_imports` is an import probe, not a package declaration. Every probe
must have an owner: a non-empty `dependencies` list, or a named
`resources.environment`. The audit covers the whole catalog, not only changed
operators, and checks ownership rather than package-name normalization. This
closes the class of defect where repair silently skips an operator because
`dependencies` is empty.

Pass criterion: zero failures in the focused set; the composition matrix and
dependency audit pass for the whole catalog; every skip has a concrete reason.
A test that cannot run because an optional dependency is absent is `SKIP_DEP`;
it does not fail the layer, but the affected operator cannot claim a numerical
oracle in that environment.

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

## 7. L5 — release-artifact installation and runtime acceptance

Purpose: prove that the **exact zip users download** installs into a clean
profile and runs where it is installed. Source-tree execution, a rebuilt bundle
or a build-compatibility run is not L5 evidence.

Normative rules:

1. **Freeze the artifact first.** Build the release bundle once, record its
   SHA256, and use that path for every L5 command. Rebuilding after L5 starts
   invalidates the evidence.
2. **Install the artifact, not the checkout.** Use a fresh application profile
   with no previously installed library. Install the `.operon-library.zip`
   through the application library-install API or UI. Record the application
   version, OS, profile root, install exit code, installed library version and
   the active source root. The source root must be inside the profile.
3. **Prove source identity.** Compare the installed source root with the frozen
   bundle digest. If the application reports that the bundle upgraded a factory
   seed, record both the baseline and the installed version.
4. **Prepare environments from the installed library.** For every environment
   added or changed in the release, call the environment installer through the
   installed library, not from the checkout. Record the receipt
   `spec_sha256`, interpreter path, byte/file count, every declared import and a
   real tool invocation. A manifest that only parses is not installation.
5. **Run an operator route from the installed library.** Execute at least one
   changed operator through the application CLI, HTTP or MCP adapter, using the
   installed source root. Record input hashes, output artifact hashes and the
   numeric values. Compare with the L3 source-tree run; differences need an
   explicit tolerance and explanation.
6. **Test the target runtime.** Minimum and target application versions must be
   installed and run separately. A `verify_library_release.py` run against the
   build application is build compatibility only; it does not satisfy L5.
7. **Test each claimed OS.** A Linux-only run cannot support a Windows claim.
   UI automation remains optional, but when skipped say so and do not claim UI
   verification.
8. **Write evidence before publishing.** L5 evidence is generated from the
   frozen artifact and committed before the tag is pushed. It cannot be filled
   in after the release.

Pass criterion: the frozen bundle installs, activates, prepares every changed
environment and runs the changed operator on every application version and OS
claimed in the release note. Any missing step is `verification incomplete`, not
`PASS`, and blocks the release.

## 8. Change impact matrix

| Change | L1 | L2 | L3 | L4 | L5 |
| --- | --- | --- | --- | --- | --- |
| Operator source only | required | required | affected routes | full suite | install + one route |
| Operator contract / `info` | required | required | affected routes | full suite | install + route import |
| Reader source or selection | required | required | affected routes | full suite | install + route import |
| Route `task.yaml` | required | not required | required | full suite | route import |
| Manifest / packaging | required | archive tests | not required | required | install + environment prepare + operator route |
| Version / release metadata only | required | not required | not required | full suite | install + one route |
| Documentation only | docs check | not required | not required | not required | not required |

"Affected routes" means every route that references the changed operator,
Reader or contract, not only the route named in the release note.

## 9. Release gate

A release may be tagged or published only when:

1. L1 and L4 are `PASS`, including the catalog-wide dependency audit.
2. L2 is `PASS` for every changed operator/Reader, including the composition
   matrix for every declared dimension and label.
3. L3 is `PASS` for every changed route.
4. L5 is `PASS` for the **frozen artifact**: clean install, environment
   preparation and operator smoke on every application version and OS named in
   the release note. Source-tree tests and build-compatibility runs are not a
   substitute.
5. The L5 JSON records the artifact SHA256, installed source root, application
   version, environment receipt and route artifact hashes; it matches the
   tagged commit and the uploaded assets.
6. Any `SKIP` is listed in the release note with reason, owner and impact.
7. The evidence file matches the tagged commit.

A hotfix may shorten the schedule, not the evidence. If a layer cannot run, the
release note says which layer is missing and the release is marked
`verification incomplete`; it is not described as fully tested. Manual
publication is not an exception: the publisher must run
`scripts/check_release_acceptance.py` against the frozen artifact and the
committed acceptance JSON before creating the release.

## 10. Evidence file

Store one JSON file per release, for example
`verification/release-acceptance-<version>.json`, plus raw logs under the same
directory. The file is generated from the frozen artifact and is a release
blocker, not a post-release note.

```json
{
  "schema_version": 1,
  "library_version": "8.0.8",
  "commit": "4a566727",
  "bundle": {
    "asset": "Operon-Library-v8.0.8-Linux.operon-library.zip",
    "sha256": "e4884979..."
  },
  "application": "4.1.9",
  "os": "windows",
  "profile": {"clean": true, "root": "<profile>"},
  "install": {
    "status": "PASS",
    "installed_version": "8.0.8",
    "source_root": "<profile>/library/8.0.8",
    "exit_code": 0
  },
  "environment": {
    "name": "openmm81",
    "status": "PASS",
    "spec_sha256": "59c91e69...",
    "interpreter": "<profile>/.../python.exe",
    "bytes": 154686868,
    "files": 3748,
    "imports": ["openmm", "numpy"],
    "tool_probe": "PDBFixer 1MEL -> 8247 atoms / 587 residues"
  },
  "operator": {
    "id": "interface_alanine_scan",
    "status": "PASS",
    "command": "operon ...",
    "input_sha256": ["..."],
    "outputs": [{"name": "alanine.csv", "sha256": "..."}]
  },
  "layers": {
    "L1": {"status": "PASS", "checks": []},
    "L2": {"status": "PASS", "summary": {"passed": 0, "failed": 0, "skipped": 0}},
    "L3": {"status": "PASS", "routes": []},
    "L4": {"status": "PASS", "pytest": {"passed": 0, "failed": 0, "skipped": 0}},
    "L5": {"status": "PASS", "summary": "frozen artifact installed and ran"}
  },
  "release_blocking": []
}
```

`bundle.sha256` must equal the uploaded asset digest. `install.source_root` must
be inside the clean profile. `environment.spec_sha256` must match the receipt
created by the installed library. `operator.outputs` must be hashes of files
produced by the installed route, not copied from a source-tree run.

## 11. Lessons that changed this standard

| Incident | What passed | What users saw | Rule now |
| --- | --- | --- | --- |
| 8.0.7 `openmm81` | Source-tree environment probe and 4.0.8 build verify | `pkg_resources` missing; micromamba CRL failure; GitHub tarball timeout | Prepare from the installed library and run the real tool; no source-tree substitute |
| 8.0.8 PDBFixer | Bundled files, source probe, 4.0.8 forward verify | Environment worked, but the final bundle was not installed into 4.1.9 before publish | L5 must install the frozen artifact and run an operator from it |
| 8.0.3/8.0.4 contracts | Positive contract sample | `join`/`aggregate` failed on labels that were never exercised | Exact-compatible composition matrix, every declared dimension and label |
| 8.0.5 doc hashes | Tests and registry check | CI verify failed because generated doc hashes were stale | Rebuild docs, registry and packages before freezing the artifact |
| 8.0.6 Routes | Library bundle verified | Release failed because `Operon-Routes-*.zip` was never packaged | Build every asset declared in the release note; checksum the frozen set |

The general rule: a test that runs in a different root, with a different
artifact, or against a different application version is a useful pre-check,
not release acceptance.

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

### 8.0.2 per-operator coverage round

Tested on the native 8.0.2 worktree (`/home/gavin/Operon-7015-native`).

| Layer | Result | Evidence |
| --- | --- | --- |
| L1 | PASS — 1063 operators, 0 FAIL, 0 SKIP | `verification/coverage-8.0.1/summary.json` |
| L2 | PASS — 11 oracle, 8 smoke, 1044 unit, 0 SKIP | `verification/coverage-8.0.1/operator_coverage.csv` |
| L3 | 223 local + 47 server executions, 789 compiled routes, 4 SKIP | `verification/coverage-8.0.1/l3_skips.json` |
| L4 | 37 measured (36 deterministic), 1026 estimates, 0 SKIP | `verification/operator-audit-8.0.1/l4_determinism.json` |
| L5 | 984 installed descriptors, 79/79 route bundles valid, 0 SKIP | `verification/operator-audit-8.0.2/operator_table.csv` |

The four L3 SKIPs are three Boltz operators (no Boltz runtime or weights) and
RFdiffusion (no compatible generic checkpoint; official GPU DGL ABI mismatch;
CPU exceeded the 1800 s designer timeout). L4 `ESTIMATE` rows are resource
declarations, not measured memory traces; they are never promoted to `MEASURED`
in the trust sheets. Studio UI automation remains a SKIP.

Per-operator evidence: `verification/coverage-8.0.1/operator_coverage.csv` and
`docs/operators/<id>.md`.

## Appendix B — command template

```bash
cd /path/to/Operon-worktree
export PY=/path/to/python
$PY -m operon registry check --json
$PY scripts/build_operator_docs.py --check
$PY scripts/audit_portability.py
$PY -m pytest -q tests/test_upstream_operators.py tests/test_builtin_routes.py \
  tests/test_contracts.py tests/test_library_release.py \
  tests/test_contract_compositions.py tests/test_interface_contracts.py \n  tests/test_release_acceptance.py
$PY scripts/run.py /tmp/routes/gwas --check
$PY scripts/run.py /tmp/routes/gwas
$PY -m pytest -q
$PY scripts/release_library.py --tag library-v<version> --output /tmp/build-<version>
$PY scripts/verify_library_release.py --bundle /tmp/build-<version>/Operon-Library-v<version>-Linux.operon-library.zip  # build compatibility, not L5
 -I scripts/check_release_acceptance.py verification/release-acceptance-<version>.json \n  --bundle /tmp/build-<version>/Operon-Library-v<version>-Linux.operon-library.zip  # L5 gate
```
