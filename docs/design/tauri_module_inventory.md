# Operon desktop migration: module inventory

Status: design for an experimental shell, not a production migration. Baseline:
Operon 5.2.0, commit `7ee161528ae24d7c8e136ba8c48bfe94b6b77e99` plus the
`feature/canvas-runplan` integration. Do not change the library or scientific SDK
as a side effect of replacing the shell. Read `tauri_implementation_contract.md`
and `tauri_coding_instructions.md` before writing Rust.

## 1. Boundaries and dependency direction

```text
Windows C# host (experimental replacement: Rust/Tauri)
  -> authenticated local management service
  -> React canvas / API / CLI / MCP
  -> Application services
       -> workflow compiler -> frozen RunPlan
       -> canvas preparation -> code + environment bindings
       -> host pool -> coordinator -> supervisor -> invocation adapters
            -> Python Context / R / native processes -> committed artifacts
       -> SSH transport -> server Application -> server host pool
       -> standalone exporter -> independent package and runner
```

The shell owns windows, bootstrap and lifecycle, not jobs. React owns editing
and presentation, not dependency installation or scheduling. Python management
owns durable state, authorization, compilation and execution requests. Scientific
workers own computation. The operator library is a separately distributed input.

## 2. Current desktop shell (replace behind a stable adapter)

| Component | Responsibility and invariants | Tauri disposition |
|---|---|---|
| `desktop/Program.cs` | WinForms window, WebView2, loopback startup, ready/draft-close handshake, tray and close decisions | Replace presentation/lifecycle only; preserve close ordering |
| `desktop/ProcessLifetime.cs` | Owned process lifetime, child cleanup and exit observation | Implement Rust ownership guard; never enumerate and kill arbitrary Python |
| `desktop/RuntimeLocator.cs` | Find the selected management Python and installation metadata | Read the same installation contract; no PATH-first guessing |
| `desktop/RuntimePreferences.cs` | Runtime preference persistence and installation isolation | Keep explicit scope; experimental profile cannot overwrite global production configuration |
| `desktop/IsolatedEnvironment.cs` | Construct child environment without contaminating other installations | Port allowlist and absolute owned paths |
| `desktop/RuntimeSelectionDialog.cs` | User-facing recovery when a management runtime is unavailable | First experiment uses a supplied managed runtime; later implement equivalent recovery |
| `desktop/WebViewBootstrap.cs` | WebView2 availability/bootstrap | Tauri's Windows WebView2 handling; test offline/missing-runtime behavior |
| `desktop/DesktopLog.cs` | Early startup and host failures, before the server is ready | Structured Rust log with existing diagnostic directory convention |
| `desktop/Autostart.cs`, `ShortcutRepair.cs` | Startup integration and shortcut repair | Experimental identifiers/shortcuts only; opt-in, no takeover |
| `desktop/operon-desktop.json` | Host deployment configuration | Translate via typed `HostConfig`, do not duplicate secrets into frontend state |
| `desktop/OperonStudio.csproj` | .NET 8, WinForms, WebView2, icon, self-contained binary | Leave production build unchanged |

Current host web messages include `studio-ready`, `draft-saved`,
`draft-save-failed`; host requests `prepare-close`. Treat those as a lifecycle
contract, not as arbitrary JavaScript evaluation hooks. Investigate the exact
close/maintenance behavior in the current source before replacing it.

## 3. Frontend (reuse)

Current versions declared by `frontend/package.json`: React 19.2, TypeScript 5.9,
Vite 7.3, XYFlow 12.10, Phosphor 2.1.9, Vitest 4.1.11. Preserve the checked-in
lockfile; do not upgrade dependencies as part of the host experiment.

| Area | Sources | Responsibilities |
|---|---|---|
| Composition / editing | `frontend/src/App.tsx`, graph utilities and node components | Multi-document canvas, selection, drag/connect, clipboard, undo, operator inspection |
| HTTP transport | `api.ts`, `planApi.ts` | Authenticated requests, structured errors, binary result opening; no scientific logic |
| Automatic RunPlan UI | `CanvasPlanDialog.tsx` | Frozen preparation, original action IDs, progress, run/export history |
| Advanced RunPlan UI | `PlanPanel.tsx`, `planState.ts`, `planTypes.ts` | Explicit authoring/plan import, bounded persistent UI receipts, exact-body retry |
| Results | `PlanRunResults.tsx`, original results components | Bounded events/logs/files, committed artifact previews, original PNG/PDF/SVG |
| Export | `PlanExportPanel.tsx` | Advanced explicit export; automatic canvas export uses generated manifests |
| Storage/server panels | Existing remote/storage UI and API clients | Select authorized server data and configure connections; keep credentials out of graph JSON |
| Settings / language | Existing settings components, `i18n` and JSON dictionaries | Language/theme/viewer preferences, shared profile configuration |
| Visual system | Stylesheets, Geist fonts, Phosphor assets | Reuse unchanged; Tauri is not a redesign project |

Do not create a second React application. Introduce one `desktopHost` interface
with browser, current WebView2 and experimental Tauri implementations. Components
may not import Tauri APIs directly. This allows browser development and current
desktop releases to continue during the experiment.

## 4. Management service (retain Python)

| Area | Sources | Contract |
|---|---|---|
| Composition | `operon/application.py` | Profile/workspace services and shared API/CLI/MCP boundary |
| Workflows | `operon/documents.py`, workflow service, `src/web/parameters.py`, routes | Versioned graphs, frozen parameter values, route expansion, migration |
| HTTP | `src/web/api.py`, `operon/control_api.py`, `plan_api.py`, `canvas_api.py` | Auth scopes, bounded offload, JSON errors, streaming file responses |
| Agent | `operon/cli.py`, MCP and agent service modules | Headless functionality, selection/context, batch edits, single undo, stable submissions |
| Readiness | `operon/readiness.py`, dependencies, environment install | Dependencies-only checks separate from execution validation; explicit installation |
| Storage | `operon/storage/` | Authorized roots, StorageRef version/digest, bounded browse/stat/transfer |
| Results/viewers | `plan_results.py`, `plan_artifacts.py`, `viewers.py`, task file services | Ownership checks, immutable committed files, bounded preview and explicit desktop opening |
| Remote | `operon/remote/`, `src/web/remote_service.py`, transfers | SSH credentials/host keys, capabilities, resumable content-verified movement |
| Canvas preparation | `canvas_plans.py`, `export/automatic.py`, `environment_store/canvas.py` | Generate code/resource/environment bindings; no scheduling authority |

The management process remains necessary for UI state and local protocols even
when science runs remotely. A thin Tauri host does not mean starting a scientific
Python environment on application launch. A minimal management runtime and a
chosen scientific runtime remain different concepts.

## 5. Compiler, execution and storage (do not rewrite in Rust)

| Layer | Sources | Must preserve |
|---|---|---|
| Contracts | `operon/contracts/` | Strict canonical JSON, domain-separated identities, typed paths and environment requirements |
| Compiler | `operon/planning/` | One compiler for graph/YAML, route expansion, conversion contracts, independent parameter JSON |
| Native execution | `operon/execution/context_bridge.py`, worker, native adapter | Existing `src.task.Context`, memory allocation, spill, streaming and output semantics |
| Other languages | Invocation lowering, command adapter, codecs | Explicit files/Form boundaries, per-language executable, full process resource accounting |
| Environment generations | `operon/environment_store/` | Locked archives, package-level verification, leases, relocation probes, GC |
| Coordination | `operon/pool_service.py`, `operon/engine/` | Single resource authority per pool, durable idempotency, fair admission and confirmed process-tree exit |
| Cluster | `operon/cluster/` | Controller fences, placement, PostgreSQL where configured; multi-host/Slurm remain experimental |
| Scientific data | `src/core/`, `src/task/memory/`, reader execution | Form/axis metadata, disk-backed arrays, bounded transport, no JSON serialization of full matrices |
| Export | `operon/export/`, `plan_export_service.py` | Same RunPlan, generated source manifests, isolated environments, independent launchers and relocation verification |

## 6. Packaging and ownership

Windows Setup and its uninstall/upgrade ownership protections remain the release
authority. Linux distribution remains headless Python plus the server entrypoint.
The experimental host must be independently installable and uninstallable. An
app-window close is not an instruction to terminate a shared server pool.

Code/resources may be copied from installed providers during preparation; this
is not modifying or republishing `library/`. Do not change operator declarations,
seed packages, protocol revisions, or library version numbers for the shell.

## 7. Measurable constraints

Record current and experimental startup-to-interactive, draft flush, shutdown,
idle RSS, first/reused preparation, and artifact opening. Tauri may reduce shell
payload but cannot eliminate Python/R/scientific dependencies from a complete
offline environment. Keep management-only and full-runtime package sizes separate.

Performance claims require measurements on the same machine, profile, canvas,
dependency state and warm/cold cache condition. Synthetic IPC latency is not
scientific workflow throughput.
