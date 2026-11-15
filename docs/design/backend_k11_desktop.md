# Desktop RunPlan adapter

The toolbar **Run plans** entry opens a separate dialog. The existing canvas
**Run** action keeps its current behavior; this dialog does not replace its
scheduler, admission policy or workflow settings.

## Prepare and run

1. Choose **Compile snapshot** to compile the current canvas, or import a JSON
   graph, strict compile request, RunPlan, or `{plan, binding}` manifest. An
   authoring-v2 compile request includes its explicit parameter/input/environment
   sidecars. Import does not edit the open canvas or execute the manifest.
2. Inspect the fixed plan's identity, parameter fingerprint and execution units.
   Compilation alone does **not** prove that environments or inputs are ready.
3. Enter the program directory and immutable environment-store directory,
   relative to the connected application service's workspace. Choose
   **Check environments and inputs** to inspect exact prepared generations.
   Only verified compatible generations are offered; the dialog does not scan
   arbitrary interpreters or install scientific dependencies.
4. Supply any named input paths and their explicit representations, then check
   them to obtain byte sizes and streamed fingerprints. Representation selection
   is a declaration, not a conversion. Supply required storage-root mappings.
   An existing binding JSON may also be imported; the authoritative submission
   service revalidates every immutable binding and the plan identity.
5. **Submit this plan** explicitly saves the exact request and stable request ID
   before contacting the shared plan service. It does not use current defaults
   or later canvas edits. A failed history write prevents submission.

Missing generations remain visible as missing. This UI does not claim that a
traditional canvas runtime is already an immutable RunPlan environment. Use the
existing generation preparation tools or an administrator-prepared manifest.
Multiple-host and Slurm placement is labeled **Experimental**; this adapter's
tests are not evidence of dual-host or real Slurm execution.

## Receipts and recovery

Plan history is stored in a workspace-keyed file under the profile's `plan-ui`
directory, rather than a loopback-port-specific browser store. A strict revision
check prevents another desktop/agent from overwriting newer history. Request
bodies cannot change under the same ID. Pending/unknown submissions cannot be
silently discarded. History allows 20 submissions and 20 export receipts, with a
4 MiB serialized record budget; capacity errors occur before submitting work.
Confirmed run entries may be archived from this desktop list without cancelling
or deleting their server-side runs.

An unavailable response leaves the submission pending or unknown. Reopening the
dialog restores its exact body. **Confirm using original request** sends that
same body and request ID, relying on the existing pool's idempotency receipt.
There is no automatic resubmission, fresh-key retry or fallback local execution.

Observation uses one bounded request cycle at a time: compact status, one page
of attempts/artifacts, and one retained event page. Pages contain at most 30 rows
and 16 KiB. The event display retains at most 100 records. Expired event cursors
show a visible history gap and require explicitly continuing from the retained
floor. Closing the dialog aborts polling and pending reads; it does not cancel a
scientific run. Cancellation is a separate explicit action.

Logs are read on request in 16 KiB byte segments; the visible buffer retains the
last 64 KiB. Committed artifact files have opaque IDs and bounded text previews.
Safe raster/PDF originals open through an authenticated blob in a separate view;
other formats, including SVG and HTML, have an explicit **Save original** action.
No caller-selected filesystem path is used to open a result. A remote host that
does not support full artifact relay returns `artifact_transfer_required`.
Native third-party viewer launch remains in the existing job-results interface;
the new plan interface does not claim that integration yet.

## Standalone export

Import an export-resource manifest with source root, immutable environments and
explicit implementation/resource hashes. The UI shows resource counts and an
editable destination path; it does not invent code manifests from a successful
compile. **Build standalone package** uses `/api/v1/plan-exports` and saves its
original request before submission. Reopen the export history to query a receipt
by ID, or recover an unavailable response by its stable request key. Manual retry
uses the same request. Unknown completion never triggers an automatic rebuild.
The existing export service owns package construction, probes and cancellation.

## Verification boundary

The focused tests exercise authenticated adapters, bounded queries, immutable
snapshots, pre-submit persistence, conflict rejection, unknown-response recovery,
unmount cancellation, verified-generation choices, English rendering and
experimental labels. They do not prove a Windows desktop installation, a real
scientific run, an offline relocated export, dual-host execution or Slurm. Use the
release acceptance fixture and actual desktop checks for those separate gates.
