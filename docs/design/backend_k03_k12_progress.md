# K03–K12 development and acceptance ledger

This is a development ledger, **not a release or full K03–K12 acceptance claim**.
Work remains on `backend/5.1.9-cluster`, based on
`600eed6f53b6db01f7391f408ade1e950d8679b3`. The application version is 5.1.9.
The operator library is unchanged. No commit, push or publication was performed.
The protected earlier worktree was not reset, stashed or cleaned.

K00–K02 evidence remains in `backend_k00_k02_acceptance.md`. Its earlier K03
status describes that checkpoint, not the work recorded below. The user requested
development first and grouped verification; targeted repeats address observed
failures rather than repeating unrelated suites.

| Gate | Module implementation | Product integration | Actual acceptance and remaining boundary |
|---|---|---|---|
| K03 | Content-addressed environments, exact archive/wheel locks, streamed inventory, relocation probes, publication recovery, conservative leases/GC | Invocation supervisor binds the verified generation; Windows Job Objects and Linux subreaper retain ownership until the complete tree exits; definite preparation failures get an atomic negative receipt | Real Python generations built on Windows and Linux; real R/native generations on Windows. Crash/unknown-spawn cases have focused tests. Existing mutable environment preparation remains a separate explicit compatibility path; arbitrary resolver/renv/toolchain closure is not implied. |
| K04 | Shared unit executor and tagged Form/NPY/JSON/file boundaries; literal argv Python/R/native adapters | Native reader/operator to Python handoff, frozen parameters, process reservations and cancellation use the same pool/supervisor | Windows Python → R → C → Python branch/join, resume and changed values passed. Windows R needs a short physical work directory; unsupported layouts fail before launch. This is not arbitrary long-path R support or automatic streaming of legacy readers. |
| K05 | Explicit kernel/resource collector, immutable environment payloads, portable build receipts, shared standalone kernel and verified resume | New asynchronous plan export through CLI/API/MCP, separate from old workflow export; the resulting bundle runs without an installed Operon application | Moved Windows native and mixed-language packages tested with isolated HOME/PATH. Linux export omitted a dynamically launched subreaper file; corrected and covered by the explicit collector test. See the acceptance record for subsequent real Linux results. |
| K06 | Strict authoring-v2 vocabulary and sidecars; one compiler for graph/YAML and frozen replay | Plan compile, submit, status, cancel and export share Application services | Frozen parameter entries replace declaration-derived values completely, including removed keys. Contract/YAML/kernel group: 106 passed. Nextflow-inspired authoring is not direct Nextflow DSL2 execution compatibility. |
| K07 | Bounded local/SFTP browse, preview, cursor and cancellation; separately verified bastion/target keys | Storage API/CLI and configured-mount file picker in settings | Local and mocked SFTP boundary tests passed. Actual provider gateway did not expose a usable SSH/SFTP channel; web terminal testing is not SFTP/bastion acceptance. Existing input editing and shared storage execution bindings still need remaining UI/product integration. |
| K08 | PostgreSQL 17 migrations, transactional admission/dedupe/quotas, durable leadership/outbox, bounded lanes | Cluster controller repository and host-facing requests | 11 tests passed against a real owned PostgreSQL 17.12 process, then that process stopped. This does not establish controller + remote multi-host failover or load qualification. |
| K09 | Placement, fenced host requests, durable producer/consumer preparation and artifact retention pins | Actual host pool RPC supports native producer → Form → Python consumer, replay dedupe, cancellation and verified releases | One-host TCP RPC passed on Windows and Linux. Only one Linux host was available. Two-host SSH, cross-host transfer and failover remain unaccepted; unsupported transfer/native alias mappings fail explicitly. |
| K10 | Slurm request/token reconciliation, allocation adapter and cancellation boundaries | Adapter-level integration only | No actual Slurm site was available. Unit tests are not scheduler/accounting acceptance. |
| K11 | Shared plan/storage/export services and bounded result read model | CLI, HTTP and MCP compile/submit/status/cancel/events/attempts/logs/artifacts share existing permissions and pool authority; frontend storage picker builds | Result reads have grouped tests; logs use owned attempt IDs, no caller paths. Artifact API lists committed group metadata, not arbitrary previews/downloads. New plan UI, remote artifact relay and complete professional-viewer path are not accepted by these tests. |
| K12 | Development wheel built with contracts, SQL migrations, containment helper and path validator verified in its payload | No released package integration yet | No new Windows Setup/shortcut or exact Linux release archive acceptance; no version bump or release. Do not call K12 complete. |

## Corrections found by actual execution

- Windows python.exe can be shorter than MAX_PATH while a loaded .pyd is longer.
  Preserve the adapter's explicit extended executable spelling through LaunchSpec.
- Case-insensitive lookup mistook imported Context for the context module.
  Collector traversal now verifies exact component spelling. Lazy SDK/Context
  modules and the Linux subreaper are explicit kernel resources.
- A script fixture hashed LF bytes but wrote CRLF on Windows. Fixture bytes now
  match their frozen digest; runtime integrity checks were not relaxed.
- Artifact confinement now resolves with the same extended Windows spelling used
  for stat, retaining all link/reparse and final-content checks.
- Command preparation can fail before launch. An atomic fenced negative receipt
  distinguishes this from unknown outcomes. Missing, conflicting or malformed
  evidence never proves a stopped process or releases a grant.
- Event retention uses a monotonic maximum deleted cursor, checked under the
  state lock; older retained-floor records are handled explicitly.
- R normalizes junction targets and has physical path/temp constraints. A failed
  alias experiment was removed. The supported path is an explicitly selected
  short physical work partition, with early validation.
- Linux cancellation needs an explicit monitor-ready handshake; a returned PID
  alone does not prove that signal handlers have been installed. A bounded
  readiness timeout retains ownership rather than fabricating a stopped tree.
- Coordinator shutdown retains its thread and ownership when the join deadline
  expires. Pool shutdown retains its handles and is retryable in that case.

## Evidence and operational boundaries

See `backend_k03_k12_acceptance.md` for per-batch results and exclusions.
Overlapping reruns are not added into a fabricated grand total.
`windows_foreign_runtime_paths.md` documents the R limitation;
`backend_cli_quickstart.md` documents the explicit development workflow.

The real Linux host is a single 0.5-CPU/1-GiB container reached through its
provider web terminal. These are functional checks, not throughput/latency
benchmarks. No second server or Slurm resource was provisioned. Credentials
are not recorded in source, artifacts or documentation. Shutdown uses the
provider console for the current instance, not an older instance API.

