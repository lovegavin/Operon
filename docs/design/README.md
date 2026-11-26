# Design notes

Design records for the application: why the engine is shaped the way it is,
what a past refactor had to preserve, and which pieces are still proposals.
These are working notes for maintainers, not user documentation — if you want to
run Operon, start at [../README.md](../README.md) or
[docs/quickstart.md](../quickstart.md).

A note's status line is authoritative about itself: several documents here are
explicitly "proposal, not delivered" or "implementation prepared, acceptance
pending". Do not read a design record as evidence that the behaviour ships.

## Contracts and process

Read these before changing backend or desktop code.

| Document | What it fixes |
| --- | --- |
| [backend_implementation_contract.md](backend_implementation_contract.md) | Normative contract for the execution backend: ownership, states, invariants. |
| [backend_coding_instructions.md](backend_coding_instructions.md) | How to implement that contract without violating it. |
| [engine_locking.md](engine_locking.md) | Engine lock and ownership order between adapters. |
| [agent_working_notes.md](agent_working_notes.md) | Process rules for agents extending or debugging Operon. |

## Server engine build (K-series)

The engine was rebuilt in numbered stages. The `backend_k*` notes are the work
ledger for those stages; `server_engine_*` covers the same engine from the
control-plane and acceptance side. Together they explain why the current engine
has a single-writer journal, revision checks and a resumable event log.

| Stage | Notes |
| --- | --- |
| K00 baseline | [backend_k00_inventory.md](backend_k00_inventory.md) |
| K00–K02 gate | [backend_k00_k02_acceptance.md](backend_k00_k02_acceptance.md), [backend_k02_review.md](backend_k02_review.md) (historical failure review), [backend_control_performance.md](backend_control_performance.md) |
| K03–K05 immutable environments | [backend_k03_k05.md](backend_k03_k05.md) |
| K03–K12 ledger | [backend_k03_k12_progress.md](backend_k03_k12_progress.md), [backend_k03_k12_acceptance.md](backend_k03_k12_acceptance.md) |
| K06 authoring v2 | [backend_k06.md](backend_k06.md) |
| K07 storage | [backend_k07.md](backend_k07.md) |
| K08–K10 cluster foundation | [backend_k08_k10.md](backend_k08_k10.md) |
| K11 plans and artifacts | [backend_k11_plans.md](backend_k11_plans.md), [backend_k11_plan_artifacts.md](backend_k11_plan_artifacts.md), [backend_k11_plan_exports.md](backend_k11_plan_exports.md), [backend_k11_desktop.md](backend_k11_desktop.md) |
| Engine, control plane | [server_engine_baseline.md](server_engine_baseline.md), [server_engine_implementation_plan.md](server_engine_implementation_plan.md), [server_engine_progress.md](server_engine_progress.md), [server_engine_next.md](server_engine_next.md), [server_engine_acceptance.md](server_engine_acceptance.md) |
| CLI for backend work | [backend_cli_quickstart.md](backend_cli_quickstart.md) |

## Execution, plans and portability

| Document | Subject |
| --- | --- |
| [execution_portability_cluster_roadmap.md](execution_portability_cluster_roadmap.md) | Roadmap from local execution to portable packages and clusters (proposal). |
| [canvas_runplan_integration.md](canvas_runplan_integration.md) | Canvas runs go through the same frozen RunPlan as CLI and API. |
| [node_discovery.md](node_discovery.md) | Discover compute nodes and place work by free capacity (5.10). |
| [pool_service.md](pool_service.md) | Shared multi-workspace pool as the default execution authority. |
| [pool_linux_acceptance.md](pool_linux_acceptance.md) | Real Linux/SSH pool acceptance evidence. |
| [hard_capability_status.md](hard_capability_status.md) | Which long-running hard capabilities are verified end to end. |
| [hard_queue_status.md](hard_queue_status.md) | Queue status for those capabilities. |

## Library, extensions and routes

| Document | Subject |
| --- | --- |
| [library-application-split.md](library-application-split.md) | Proposed full library/application split (and [Chinese version](library-application-split.zh.md)). |
| [port_contract_inventory.md](port_contract_inventory.md) | Frozen port inventory behind the 5.8.2 port rule. |
| [extension_policy.md](extension_policy.md) | What belongs in the core library and what is left to plugins. |
| [route-collections.md](route-collections.md) | Route collections: importing a ZIP of saved routes. |
| [competitive_landscape.md](competitive_landscape.md) | Where Operon actually differs from competing platforms. |
| [minibinder_vhh_design_route.md](minibinder_vhh_design_route.md) | What the library can do today for minibinders and VHH. |

## Desktop, web and interaction

| Document | Subject |
| --- | --- |
| [ui-action-matrix.md](ui-action-matrix.md) | Static audit of every interactive control, traced to its React handler and auth regime. |
| [frontend_interaction_review_2026-11-09.md](frontend_interaction_review_2026-11-09.md) | Review of update lifecycle and workflow feedback. |
| [pending-resource-ui-fixes.md](pending-resource-ui-fixes.md) | Four reproduced defects from the 5.7.23 cycle. |
| [mcp_http_parity.md](mcp_http_parity.md) | Parity between frontend API calls, MCP tools and CLI commands. |
| [windows_foreign_runtime_paths.md](windows_foreign_runtime_paths.md) | Extended-length path constraints for Python and native executables. |

## Incidents

[remote_recovery_incident.md](remote_recovery_incident.md) separates confirmed
application defects from hypotheses after a remote recovery failure; it is the
model to follow when writing a post-incident note.

## See also

- [docs/verification/README.md](../verification/README.md) — what was tested and when.
- [docs/releases/README.md](../releases/README.md) — release history.
