# Tauri host bridge v1: shared T01 contract

Status: contract v1 for Session A. Session B adapters are not yet implemented.
No Tauri native adapter, Rust crate, shell command or filesystem capability is
introduced by this contract. The existing C# host remains the only WebView2
desktop host.

Source of truth for shared TypeScript types:
`frontend/src/host/types.ts`.

## 1. The six methods are fixed

```ts
interface DesktopHost {
  readonly kind: 'browser' | 'webview2' | 'tauri';
  ready(): Promise<void>;
  acknowledgeDraftFlush(requestId: string, saved: boolean): Promise<void>;
  showDiagnostics(): Promise<void>;
  requestFullExit(): Promise<void>;
  openCommittedArtifact(runId: string, artifactId: string, fileId: string): Promise<void>;
  onPrepareClose(handler: (requestId: string) => void): () => void;
}
```

Do not add exec, shell, readFile, writeFile, arbitrary URL, process-inspection or
generic IPC methods. Artifact opening later resolves opaque IDs through the
authenticated backend. Existing HTTP result links remain the browser-compatible
path.

## 2. Error contract

Every rejected host operation throws `DesktopHostError`, or the adapter normalizes
a foreign host failure through `toHostError(value)` so that code that catches
errors always sees this shape:

```ts
{
  code: 'host_unsupported' | 'host_capability_unavailable'
      | 'host_request_stale' | 'host_bridge_unavailable';
  message: string;
  request_id: string | null;
  retryable: boolean;
  next_actions: ('use_tray_menu_exit' | 'open_host_logs'
      | 'use_http_artifact_link' | 'retry')[];
}
```

`DesktopHostError.toJSON()` includes `Error.message` and all five fields.
`isHostErrorShape` validates codes, non-empty message, request-ID type, boolean
`retryable` and every next action. It does not cast arbitrary objects.
`toHostError` preserves a valid shape, returns an existing `DesktopHostError`
unchanged, and maps every unknown exception to:

```ts
new DesktopHostError('host_bridge_unavailable', 'Desktop host bridge failed.')
```

Do not use an unknown exception's message in the rendered error; it may contain a
local path or credential.

## 3. Legacy WebView2 wire: exactly three replies

The current C# host (`desktop/Program.cs`, message switch and close handler)
understands only these renderer-to-host objects:

```text
{"type":"studio-ready"}
{"type":"draft-saved"}
{"type":"draft-save-failed"}
```

They must remain exactly one field. No request ID, no extra properties, no new
message type. The host-to-renderer request remains exactly
`{"type":"prepare-close"}`.

`LEGACY_WIRE` is deeply frozen. Use `createLegacyWireMessage(kind)` to allocate a
fresh object immediately before posting. Do not mutate a shared wire object.

## 4. WebView2 adapter rules (Session B)

The current C# host has one uncorrelated `draftSaved` waiter. Parallel or
out-of-order legacy acknowledgements are unsafe, even if the adapter invents
local IDs.

- `ready()` posts `studio-ready` only after the canvas bootstrap has hydrated.
  Register the close listener before posting readiness, matching the current
  `App.tsx` ordering.
- `onPrepareClose(handler)` delegates. The adapter owns one active close lifecycle:
  while a single flush is pending, repeated `prepare-close` events are coalesced
  and must not start a second flush or mint a second active ID.
- Each new close lifecycle after the previous one completed or was cancelled may
  get a fresh adapter-local ID (for example `webview2-close-<counter>`). IDs are
  adapter-local and never written to the legacy wire.
- `acknowledgeDraftFlush(id, saved)` succeeds only for the single active pending
  ID. It removes that ID and posts exactly `draft-saved` or `draft-save-failed`.
- Unknown, duplicate, stale or already-unsubscribed IDs reject with
  `host_request_stale` and emit **no** wire output.
- Calling the unsubscribe function invalidates the active pending ID and removes
  the listener. A late flush promise must fail its ACK as stale; it must never ACK
  a subsequent close lifecycle.
- `showDiagnostics()`, `requestFullExit()` and `openCommittedArtifact()` reject
  with `host_capability_unavailable` because the current C# host has no such IPC.
  Use `open_host_logs`, `use_tray_menu_exit` and `use_http_artifact_link`
  respectively. Never call `window.close()`, kill a process or open a path.
- Do not claim cross-host correlation. The legacy wire cannot observe a host
  timeout; the C# host's 5-second draft-save deadline remains authoritative and
  is not a success signal.

## 5. Browser adapter rules (Session B)

- `ready()` and `onPrepareClose()` are harmless no-ops; the unsubscribe function
  does nothing.
- `acknowledgeDraftFlush()` rejects with `host_request_stale`. A browser has no
  host `prepare-close` source, so it never has a pending close to acknowledge.
- `showDiagnostics()`, `requestFullExit()` and `openCommittedArtifact()` reject
  with `host_capability_unavailable`. They must not silently resolve and pretend
  the action happened. Do not call `window.close()`.
- Existing HTTP artifact links and all Chinese UI strings remain unchanged.

## 6. T01 App integration limits

- Wire only bootstrap readiness and the close handshake. Keep the existing draft
  flush body (agent bridge flush when active, otherwise `api.saveWorkspace`).
- T01 adds **no** File-menu or Quit control. An in-app full-exit command is a
  later Tauri capability; showing an unsupported control in the old host would be
  misleading.
- Do not edit result components, the backend, desktop/, installer/, library/,
  SDKs, versions or lockfiles.

## 7. Forward Tauri DTOs only

These are contract placeholders for a later gate. They do not authorize a native
adapter now:

```ts
interface PrepareCloseEvent {
  type: 'prepare-close';
  request_id: string;
}

interface AcknowledgeDraftFlushRequest {
  request_id: string;
  saved: boolean;
}
```

A later Tauri event must carry a host-generated `request_id`; the adapter must
reject an ACK for an ID it did not issue. Native implementation, Rust
dependencies, capabilities and installer integration are out of scope for T01.

## 8. Required focused checks for Session B

With a fake bridge and mocked events, cover:

1. Exact `studio-ready`, `draft-saved`, `draft-save-failed` JSON.
2. Repeated `prepare-close` coalescing while one flush is pending.
3. Failed flush posts `draft-save-failed`, never `draft-saved`.
4. Unknown, duplicate and stale ACKs reject with no wire output.
5. Unsubscribe removes the listener and invalidates the pending ID.
6. A late promise cannot ACK a later close lifecycle.
7. Browser capability methods reject with `host_capability_unavailable`; browser
   acknowledge rejects with `host_request_stale`.
