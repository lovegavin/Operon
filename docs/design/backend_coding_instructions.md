# Coding execution instructions: execution backend revision

Read [the implementation contract](backend_implementation_contract.md) first.
That document is normative. The older
[roadmap](execution_portability_cluster_roadmap.md) explains product intent;
where its sketches differ, use the implementation contract.

## Assignment

Implement the contract incrementally. You are implementing an already selected
architecture. Do not select an alternative framework, scheduler, queue,
database, protocol, runtime strategy or export mechanism because it is easier
to scaffold. If an invariant is impossible with the current code, demonstrate
the conflict with a concrete source path and failing test, then record a narrow
design correction before proceeding.

Start with K00-K02. Do not make a broad frontend change or create all future
modules as placeholder implementations. Advance through later K units only when
the prerequisite gate passes; independent work can proceed while a real-platform
test is awaiting infrastructure.

## 1. Protect the starting state

1. Read repository instructions and inspect all working trees/statuses.
2. Use upstream application commit
   `600eed6f53b6db01f7391f408ade1e950d8679b3` (5.1.9) as the fixed integration
   baseline. Record later upstream changes separately; do not silently chase
   moving main or merge unreviewed library updates.
3. Create an application worktree/branch under the existing BioPipe project.
   Do not change/reset/stash/clean the existing dirty checkout. Do not create a
   second project root in the parent DingLab directory.
4. Inventory and preserve local maintenance/admission/export changes. Port
   behavior and regression tests against the current `operon` namespace.
   Whole-file replacement from the older `biopipe` tree is not an acceptable
   merge strategy.
5. Keep operator/library sources and saved parameter values unchanged. The new
   application consumes library manifests/resources; library changes have a
   separate owner and version.

## 2. Fixed architecture

- CPython 3.11 management runtime; preserve its validated build, test source
  compatibility on 3.11/3.12. Scientific interpreter versions are per environment.
- Strict Pydantic 2 wire contracts; frozen engine dataclasses; existing safe
  YAML parser; explicit schema versions and canonical identity fixtures.
- One shared compiler and invocation layer for app, CLI, MCP, remote and export.
- Retain existing host StateStore, Coordinator, ProcessSupervisor, memory/spill,
  artifact commit, outbox and shared-pool lifecycle. No second host allocator.
- FastAPI/Uvicorn remains the HTTP adapter. Preserve the bounded private pool
  transport and port its local overload fixes.
- PostgreSQL 17 + psycopg 3 is only for the persistent cluster controller;
  SQLite remains local/standalone. Use explicit SQL and numbered migrations.
- Paramiko supplies SSH, jump channels and SFTP. Slurm is an executor with its
  own admission authority; SSH hosts use their existing per-host pools.
- Package actual runtime/dependency/resource files. Launch scripts invoke the
  shared minimal execution kernel; they do not contain a second DAG engine.
- Environment preparation is explicit. Managed generations are immutable;
  live attempts pin them. The application never mutates a running generation.
- Tauri, active-active HA and arbitrary Nextflow DSL parsing are outside these
  implementation units. Keep their boundaries compatible, without scaffolding
  untested substitutes.

## 3. Required first delivery

K00 output:

- protected integration branch/worktree and exact baseline inventory;
- retained author fixes: UTF-8, DLL paths, environment commit/rollback,
  installing state and PDBFixer resource manifest behavior;
- retained local Setup maintenance and bounded admission regressions;
- exact runtime/dependency manifest, import-boundary baseline and targeted test
  results, distinguishing existing failures from new failures.

K01 output:

- versioned WorkflowSpec/RunPlan/InvocationSpec/environment/storage models;
- shared compiler using metadata only, frozen parameter preservation and
  deterministic route expansion;
- schemas generated from the selected wire models, canonical hash fixtures,
  old/new format round-trip and invalid-input tests;
- explicit unsupported-boundary diagnostics; no silent graph simplification.

K02 output:

- common invocation and Context bridge behind existing Executor/Supervisor;
- a real native Reader -> PCA -> report/plot branched workflow run through the
  new path and compared with the original application path;
- preserved info/axis metadata, memory budget, logs, cancellation, native
  artifacts and process-tree cleanup;
- no full-data copy introduced merely to cross an interpreter boundary.

After these gates, continue K03-K12 as specified in the contract. Do not label
multi-language export complete until real Python/R/native code and conflicting
environment cases execute on their target platforms.

## 4. Test and reporting discipline

For each delivery update a progress table with separate columns:

| Unit | Implemented behavior | Module tests | Product integration | Real E2E | Remaining blockers |
| --- | --- | --- | --- | --- | --- |

Evidence must identify the command, source revision/dirty patch identity,
platform, interpreter, input fixture, outputs, pass/fail counts and skipped
capabilities. Preserve logs under the project diagnostics area; do not include
credentials or private user data.

Required fault cases include ambiguous commits/submissions, duplicate request
keys, environment publish crashes, surviving worker after launcher/controller
death, cancel under load, corrupt/missing outputs, disk pressure and stale fences.
Timeouts must not trigger duplicate execution. A disconnected client must not
cancel accepted work or start another allocator.

Mocks validate adapter behavior only. They do not establish real Linux, SSH
jump-host, PostgreSQL concurrency, R/native runtime, Slurm, desktop Setup or
offline-relocation acceptance. If infrastructure is unavailable, mark that gate
not run and continue independent work; never manufacture evidence or silently
reduce the acceptance scope.

Keep changes narrow enough to review. Run relevant tests after each unit; run
broader integration when changed boundaries justify it. Do not repeatedly run
unrelated full suites solely for documentation edits.

## 5. Completion and publication boundary

An implementation handoff must name delivered K units and unfinished units.
It must not claim the complete roadmap from a collection of mocked module tests.
No version bump, push, release, paid-resource start, or deletion of old user
profiles is part of this coding instruction by itself. Prepare concrete release
artifacts and their verification evidence only when the release phase is
explicitly active, and publish the tested bytes without rebuilding afterward.

Public-facing documentation remains English. Stable APIs/errors must serve
CLI/API/MCP equally; language-specific UI strings cannot become protocol values.
