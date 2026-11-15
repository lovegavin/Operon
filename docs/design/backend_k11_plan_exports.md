# Explicit RunPlan export product entry

Status: implementation and synthetic-builder tests prepared for consolidated
verification. No real export, relocation, offline execution or release acceptance
is claimed by this adapter task.

The existing `workflow export --format portable` path in `operon.portable` and
the existing graph/parameter-bundle HTTP export remain unchanged. This is a new,
explicit RunPlan export operation through `Application.plan_exports` and the
existing `operon.export.service.ExportService.build` implementation.

## Request and ownership

`PlanExportRequest` is strict, frozen and exported in the application OpenAPI
schema. It includes the canonical plan, stable request ID, workspace-relative
source root/environment store/output, frozen implementation/resource manifests,
materialized environment generation/executable bindings, management environment,
explicit input paths and input formats. Code/resource paths are confined beneath
the selected source root; that root, the environment store, every input and the
output are confined beneath the application workspace. Environment/source-root
overwrites and unknown request fields are rejected. Native sources inferred from
the plan require explicit input binding overrides; implicit external paths are
not copied into this new path.

Export builds are application-owned package construction operations, not
scientific pool runs. The facade owns no scientific allocator, scheduler, worker
process launch or environment installer. It invokes the existing builder, which
continues to own collection, content verification, relocation probes and bundle
publication. Build permission is `run` because the existing mandatory probe
executes the prepared runtime. Read permission alone can inspect receipts.

## Admission and durable receipts

One profile can have one active build and at most four waiting builds. Admission
happens before queueing; there is one build thread and no unbounded executor
queue. A separate OS file lease prevents another application instance for the
same profile from starting another build worker. The owner and short claim locks
live under `<data-dir>/plan-exports`, independently of host-pool state/locks.
Receipt retention is bounded to 1,024 claims; reaching that limit rejects new
claims and never silently discards replay records. This limit is separate from
input or exported file size.

The stable request ID determines a receipt ID, and the complete strict request
has a persisted canonical digest. Repeating the same request returns its existing
receipt before admission/path revalidation; changing content under the same key
returns `idempotency_conflict`. Receipt lookup by request ID recovers a response
lost after acceptance without resubmitting or rebuilding.

After losing the queue owner, queued/building/cancelling claims become `unknown`
with explicit inspection guidance. They are never automatically replayed. An
unknown claim also blocks a new key targeting the same unresolved output. This
slice intentionally has no adoption/force-retry/resolution endpoint; recovery
requires inspection and a separately authorized decision. Closing the application
requests cancellation of its active build and cancels queued builds; it does not
cancel scientific jobs. If shutdown/crash interrupts the builder before a terminal
receipt, the next observer reports unknown. Accepted build survival across an
application process exit is not claimed.

Queued cancellation removes the waiting item. Active cancellation signals the
existing builder callback and reports `cancelling` until the builder records a
terminal result. Cancellation racing a published completion cannot replace a
complete receipt with cancelling. The facade only records completion after the
builder returns `status: complete` and a bundle identity; this is a builder
receipt, not an independent second execution or relocation certificate.

## Shared product adapters

| API | Permission | Result |
| --- | --- | --- |
| `POST /api/v1/plan-exports` | run | 202 with durable queued/build receipt |
| `GET /api/v1/plan-exports/{id}` | context | Current receipt |
| `GET /api/v1/plan-exports/lookup?request_id=...` | context | Receipt after a lost response |
| `POST /api/v1/plan-exports/{id}/cancel` | run | Cancellation intent or current terminal receipt |

API requests enter the existing bounded application dispatcher; receipt reads and
cancellation use its reserved lifecycle lane. The build itself runs through the
separate single-worker build queue so long package assembly does not occupy all
request dispatch slots. HTTP requests do not wait for completion.

CLI:

```text
operon plan export plan.json --request export-request.json
operon plan export-status <receipt-id>
operon plan export-lookup <original-request-id>
operon plan export-cancel <receipt-id>
```

The export request file contains all request fields except `plan`, which comes
from the explicitly selected plan file. `--request-id` may provide the stable
key if absent; conflicting keys are rejected. CLI does not bypass the service or
call the old exporter. MCP tools `operon_plan_export`,
`operon_plan_export_status` and `operon_plan_export_cancel` use the same HTTP
operations; submission/cancel require the existing `--allow-run` capability.

## Verification and limits

`tests/test_plan_export_service.py` uses an injected builder to test durable
claims, replay/conflict, lookup, single-build/four-waiting bounds, queued/active
cancel, completion/cancel races, profile ownership, crash-unknown behavior,
strict paths/manifests, missing completion evidence and API/CLI/MCP permissions.
No tests were executed by this delegated implementation. Run these with the plan
service and existing export/headless regressions in the consolidated phase.

The first consolidated batch exposed Windows deep-profile I/O failures in seven
export cases. Queue directory/owner/request/receipt/index I/O now uses the shared
native path adapter; the engine filesystem primitive correction is owned by the
consolidated task. Claims are indexed before receipt publication, interrupted
indexed receipt writes recover as unknown, and failed admission/recovery releases
an unused owner lease. Additional deep-profile and interrupted-publication tests
are authored; their rerun is pending. Original deep test paths are retained.

The injected builder tests do not execute the real exporter or prove usable
runtime files. Actual collection completeness, copied input policy, target-native
runtime compatibility, offline relocated execution and scientific parity remain
the existing K04/K05/K11 acceptance gates. The facade does not silently augment or
replace those gates.

Desktop configured-file selections freeze machine-stat versions. Their export is
rejected before queue admission with `storage_route_unavailable`, because those
versions cannot authorize a relocated copy. Use the explicit portable input
import/binding with verified content; a future user-authorized verified rebind can
support this conversion. The exporter never strips a selected StorageRef or
silently substitutes the current file version.
