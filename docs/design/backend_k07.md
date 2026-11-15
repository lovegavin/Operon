# Backend K07: storage module implementation

Status: implementation prepared for consolidated verification; **K07 acceptance
is incomplete**. This report covers the storage module and bounded desktop file
browsing. It does not claim complete execution wiring, real SFTP, a real bastion
route, or multi-host acceptance.

| Unit | Implemented behavior | Module tests | Product integration | Real E2E | Remaining blockers |
| --- | --- | --- | --- | --- | --- |
| K07 | Stable storage references and explicit mount/authorization map; bounded local/SFTP list/stat/preview; cancellation; trusted Paramiko direct-tcpip jump connection | Focused tests authored in `tests/test_storage_service.py`; execution deferred to the consolidated test phase | Shared Application/HTTP/CLI adapters implemented; tests authored, not run | Not run by this implementation task | Transfer bindings and shared-storage visibility probes, real SFTP/bastion acceptance, qualification of mutation behavior on actual filesystems |
| K11 storage slice | Opt-in configured mounts, account-authenticated async endpoints, connection cleanup, bounded CLI paging and desktop browsing | `tests/test_storage_api.py`; consolidated backend evidence tracked separately | Settings/Servers browser uses authorized root refs and bounded pages/previews; scoped frontend evidence below | No real SFTP/bastion acceptance | No StorageRef-to-legacy-DataSource resolver, transfer wiring, storage registration UI or dedicated MCP storage tool |

## Boundaries changed

`operon/storage/`, `operon/storage_api.py`, focused storage tests and narrow hooks
in Application, control API, Bridge and CLI belong to this delivery. The existing
`operon.contracts.StorageRef` is reused without
changing its schema or plan identity. No library, runtime version, application
version, release, remote installation, scientific allocator or engine is changed.

- `references.py`: stable ID plus normalized relative path, immutable metadata,
  explicit errors and browse restart actions. Absolute-path imports require
  `LocalStorage.import_absolute`; the imported path must resolve under its root.
- `mounts.py`: authorized mount IDs, local filesystem access, and a storage-only
  SFTP backend. File size comes from metadata. Confined symlinks are followed;
  escaping/dangling links are listed as inaccessible and cannot be previewed.
- `browsing.py`: strict frozen request/configuration models and immutable
  results. Unknown fields, boolean integers, recursive requests, and unsupported
  alphabetical ordering are rejected. Request JSON Schemas are available through
  the models' `model_json_schema()` method for the adapter schema registry.
- `service.py`: admission before I/O, bounded enumeration handles and previews,
  scoped cursor/session cancellation, expiry and status. No worker thread or
  executor is created by this service.
- `ssh.py`: an exclusively owned SFTP connection, optionally through an
  authenticated Paramiko `direct-tcpip` channel. Both hops use the same approved
  profile host-key comparison and `HostKeyRequired` behavior as the existing
  `SSHConnection`. No `AutoAddPolicy`, shell, ProxyCommand, daemon handshake,
  application installation or scientific runtime is used.
- `configuration.py`: an optional `storage-mounts.json` with strict versioned
  local/SFTP mount declarations. No default root, existing compute profile
  migration, stored password or implicit credential loading.
- `dispatch.py` and `storage_api.py`: admission before bounded asynchronous
  offload, a separately bounded cancellation/status lane, lifecycle expiry,
  authenticated endpoints and existing error codes/actions in HTTP envelopes.

StorageRef metadata versions are observation fingerprints, **not content
digests**. `stat` does not read or hash a file, and it does not claim to verify a
digest supplied in a reference. Materialization must still verify content using
the existing transfer implementation.

## Limits and cursor behavior

Defaults: page size 200, maximum page size 1000, at most 1000 raw entries examined
per page, and a two-second cooperative page-work budget. The raw-entry limit
also applies to hidden entries, so a hidden-heavy directory cannot force a full
scan before returning an empty partial page. A network operation may run until
its channel timeout; the time budget is checked between entries. SFTP uses
`listdir_iter(read_aheads=1)` and consumes READDIR attributes for regular entries,
avoiding per-entry round trips. Symlink resolution performs additional I/O.

Order is the filesystem order. Pages are not individually sorted. An exact
page-size multiple may require a final empty page to observe EOF; there is no
unbounded lookahead or complete directory materialization.

There are at most 64 retained listing handles and two per principal. Active
storage I/O is independently admitted at eight globally and two per principal;
it is separate from scientific control and transfer dispatch. Limits are strict,
positive configuration values and appear in `StorageService.status()`.

Opaque random cursors bind principal, UI session, storage mount, directory,
hidden filter, order and observed directory revision. They have 30 seconds of
idle lifetime, refreshed on a successful page. Unknown/expired/closed cursors
return `browse_cursor_expired`; scope mismatches return `browse_cursor_scope`;
detected directory or binding changes return `browse_changed`. Each has an
explicit `restart_browse` action with `cursor: null`. Active pages are serialized
per cursor without holding the global registry lock during filesystem I/O.

`cancel`/`cancel_session` set the cancellation event and close the owned SFTP
channel to wake blocked directory work. They do not close scientific SSH control
connections or cancel accepted jobs. A pending SSH authentication cannot yet be
interrupted through the cursor; its connection/authentication timeout bounds it.

Preview defaults to 64 KiB and 100 LF-delimited rows, preserves CRLF endings, and
accepts at most 1 MiB and 10,000 rows. Output explicitly reports bytes read,
displayed rows, truncation and lossy UTF-8 decoding. It reads no extra byte to
detect EOF: metadata supplies the original size. File metadata is checked around
the bounded read. Directories and special files are not previewed.

## Application, HTTP and CLI integration

`Application.storage` owns one shared `StorageService` and bounded dispatcher.
Startup loads only the explicit optional `<data-dir>/storage-mounts.json`; a
missing file produces an empty mount map. A malformed opt-in file fails closed.
Neither the workspace nor configured legacy input roots are implicitly granted.
Embedding callers can supply `storage_mounts`, `storage_limits` and
`storage_credentials` explicitly to `Application`.

The current loopback Bridge authenticates the owner of one local profile. Mount
grants use the stable principal `profile-owner`; all authenticated context-scope
clients act under that account. Agent display names and caller JSON do not grant
authority. This is the existing single-account boundary, not new multi-user
security. UI session/cursor ownership uses an independent token fingerprint,
optionally namespaced by the bounded `X-Operon-Storage-Session` header.

An explicit local configuration looks like this (substitute an actual authorized
absolute root):

```json
{"format":"operon.storage-mounts","schema_version":1,"mounts":[
  {"kind":"local","storage_id":"research-data","root":"/authorized/data",
   "principals":["profile-owner"]}
]}
```

SFTP declarations use `kind: sftp`, an absolute POSIX `root`, an `ssh` object
containing `host`, `port`, `username`, `auth`, `key_path` and the existing approved
`host_key: {type, base64}` representation, plus an optional independent `jump`
object. These are storage-only profiles and require no Operon/Python/workspace
fields. Password/passphrase values are forbidden in the file. A `credential_id`
is resolved only through an explicitly injected credential provider; no provider
means a credential-required error. Existing key/agent authentication can work
without a credential provider. Connections remain lazy and exclusively owned.

Programmatic mount binding remains available:

```python
from operon.storage import LocalStorage, MountMap, StorageService

mounts = MountMap()
mounts.register(storage_id, LocalStorage(configured_root), principals=authorized_principals)
storage = StorageService(mounts)
page = storage.list(request, principal=authenticated_principal, session_id=ui_session_id)
```

The mounted async endpoints are `POST /api/v1/storage/browse`, `/stat`, `/preview`,
`/browse/cancel`, `/browse/close`, `GET /api/v1/storage/status` and `/roots`. Root
discovery returns only authorized StorageRefs; it does not expose native roots,
SSH settings or credentials, or open backend sessions. FastAPI exports
their strict request schemas through the existing application OpenAPI endpoint.
Admission occurs before executor submission, including per-account limits; the
dispatcher does not accumulate an unbounded executor queue. Cancellation/status
have two separately admitted lifecycle slots by default. Cancellation of an HTTP
await does not release its I/O slot until the actual synchronous work finishes.
Storage errors retain code/message/details/next_actions and receive request IDs
and applicable retry delays. `HostKeyRequired` uses the existing trust error
handling; no host key is implicitly accepted.

Bridge disconnect/revoke closes that connection's browse sessions; explicit UI
close handles tab namespaces; Application shutdown closes all handles and the
dispatcher. A bounded lifecycle maintenance task calls `expire_idle` once per
second inside the existing app lifespan. Scientific job state is unaffected.
Because directory enumeration advances a handle, replaying the same live cursor
reads its next page: clients must serialize requests and avoid replay after an
uncertain response.

CLI commands `operon storage browse <id> [path]`, `stat`, `preview`, and `status`
delegate to these endpoints with context permission. Browse defaults to one
page, supports `--page-size`, `--hidden` and `--pages 1..20`, and continues pages
within one authenticated connection. It then explicitly closes its cursor and
reports `cursor_closed`, `complete` and restart guidance; it never prints a live
cursor that its connection shutdown would invalidate. Longer interactive
pagination uses the API. Preview accepts `--bytes` and `--rows`; request limits
are validated before starting a CLI client. No storage registration UI, generic
MCP storage tool or transfer endpoint is added in this slice.

### Desktop browsing and execution boundary

Settings → Servers → **Browse configured files** opens `StorageFilePicker`
using the existing file-picker styling and shared authenticated API client.
Users can choose an authorized mount, navigate root-relative directories, show
hidden entries, request the next page, and inspect a bounded text preview. Only
the current page is retained; no complete-directory enumeration or global sort
is requested by this browser. Changed/expired cursors require an explicit reload.
Each replacement listing has a distinct UI session, so closing an old request
cannot cancel its replacement. Navigation and dialog cleanup close owned cursors.
File inspection first checks the listed metadata version; inaccessible entries
cannot be selected. Metadata versions do not replace content verification.

This entry point is a browser and preview surface. Its optional picker callback
returns a StorageRef, but it is **not connected to legacy graph DataSource
execution**. Existing SSH compute profiles and their workflow file picker are
unchanged, including the older browse implementation. No implicit mount is made
from a compute profile or workspace, and no absolute path, upload, download,
transfer or desktop data relay is inferred. A configured storage root and an
authorized resolver/materialization step are still required to use these refs
as scientific workflow inputs.

The root-run frontend batch recorded in
`verification/backend/frontend-storage-o.log` on 2026-11-14 had 49 passing tests
and one unrelated stale library-upload name assertion. The storage picker and
storage API client suites passed in that batch. The stale assertion has been
corrected to the existing bundle-owned identity contract; its rerun is pending.
This is component/API-client evidence, not browser-rendering or real SFTP
acceptance. Focused new suites are `frontend/src/StorageFilePicker.test.tsx` and
`frontend/src/api.storage.test.ts`; backend root-discovery authorization is
covered in `tests/test_storage_api.py`.

The existing transfer reuse points remain:

- `operon.remote.transfers.TransferStore`: persistent acknowledged offsets,
  bounded chunks, chunk checksums, verified objects and materialization.
- `src.web.transfers.TransferClient`: bounded upload/download, prefix
  verification and checkpoint resumption.
- `operon.remote.server.RemoteService._begin_transfer/_end_transfer`: existing
  admission-backed active transport leases, retained across bounded RPC calls.

These are compute-daemon/transport interfaces, not SFTP capabilities. A
storage-only SFTP connection cannot claim those leases or their resumable
checkpoint guarantees. This delivery deliberately does not add another transfer
engine. Storage-to-storage binding, explicit shared-storage visibility probes,
authorized direct server-to-server routes and the user-approved relay decision
still need integration with those interfaces. No transfer or desktop relay is
performed by the new service.

## Verification plan and limits

No tests were executed during this delegated implementation, as requested. The
Python sources received a static AST syntax check (15 files); that check did not
import application modules or execute test cases. The
consolidated phase should run
`python -m pytest tests/test_storage_service.py tests/test_storage_api.py`
under the recorded CPython 3.11 runtime and source-compatibility runtime. It should
then retain the existing `tests/test_remote.py`, `tests/test_remote_transfer.py`
and `tests/test_transfers.py` regressions. Record exact commands, source/dirty
patch identity, runtime, pass/fail/skip counts and logs in the shared verification
area when executed; this report does not manufacture those results.

Authored cases cover traversal/platform aliases, strict limits, paging, scoped
cursors, expiry, changed directories/mounts, handle quotas, preview byte/row
bounds, authorization, metadata version checks, symlink confinement, hidden-heavy
SFTP enumeration, READDIR metadata reuse, cancellation during and while blocked
in enumeration, explicit trust at both SSH hops and cleanup after key rejection.
The SFTP and jump adapters in these tests are synthetic. A local symlink test
skips explicitly if the operating system denies symlink creation.

Real-platform acceptance still requires an authorized storage-only SFTP service,
an actual bastion route with independent trusted destination identity, a large
directory cancellation exercise, and preview limits on that service. The one
available Linux server does not establish a two-host route or multi-host/Slurm
acceptance. Do not install or start infrastructure merely to turn these gates
green.

SFTP v3 exposes metadata with server-dependent timestamp granularity and no
atomic directory snapshot or no-follow file-open primitive. Revisions detect
observable metadata changes; same-timestamp mutations can escape that detection.
Canonical paths and file attributes are checked before/after operations, but a
hostile concurrent filesystem writer is not confined atomically by SFTP v3.
Use a server-enforced chroot/read-only storage boundary when that threat model
applies; stronger snapshot guarantees remain an explicit acceptance limitation.
Local POSIX reads use anchored no-follow descriptors; Windows previews also
verify the final path of the opened file handle. Windows directory enumeration
uses canonical path checks and metadata revisions rather than a POSIX dir-fd.

## Consolidated verification update (2026-11-14)

The earlier per-slice pending-test notes above are superseded by
`backend_k03_k12_acceptance.md`. Storage and API tests ran in the real Linux
module group (241 passed, 5 skipped across that group). Frontend storage and
library component checks ran; the bundle-owned metadata assertion was corrected
and its 13-test subset passed. The Vite production build passed. These counts
cover their named groups, not 241 actual SFTP operations.

The provider web terminal permitted real Linux invocation tests but its SSH/SFTP
gateway did not expose a usable data channel. Thus actual SFTP/bastion and
storage-to-execution binding qualification remain open.

## Desktop input selection (2026-11-15)

The source Inspector's **Choose configured file** action uses the same bounded
picker as Settings. It saves `source.storage_ref` with format
`operon.storage-input`, schema version 1, storage ID, normalized relative path,
and the selected stat version. `source.path` is its percent-encoded `storage://`
URI; credentials, mount roots and a caller-selected location cannot override it.
Old sources serialize with their existing shape. Editing a selection uses the
normal canvas transaction; copying a node preserves its reference and version.

Application preparation checks the profile-owner grant without opening files.
Validation and submission resolve an execution-only graph copy, check the saved
version, and apply existing execution input roots. A browse grant does not widen
absolute-path execution access. The worker checks the bound version again before
source registration; a queued file change fails visibly and needs explicit
reselection. RunPlan compilation retains the logical URI and versioned storage
binding; its existing executor resolves confined roots and rechecks every attempt.
The graph returned to the editor retains the saved reference.
Preflight records both the logical graph digest and the checked execution graph
digest. Submission rechecks the logical graph, resolves the selected versions
again, and requires the execution projection to match before using that exact
copy. This preserves environment freshness while keeping resolved paths out of
the saved canvas.

Local files require local execution. A storage-only SFTP mount may optionally set
`execution_profile_id` in the administrator's `storage-mounts.json`. That saved
compute profile must match the storage endpoint's host, port and username exactly
(host comparison is case-insensitive), and be the explicitly selected execution
target. Canonical SFTP confinement and the compute host's input policy still
apply. Missing mappings, automatic placement, mixed execution hosts, supplied
unverified content digests and changed versions fail before submission. No file
download, desktop relay or new allocator is introduced. Companion paths remain
existing explicit Reader parameters; selecting a primary file does not select a
multi-file dataset or transfer its siblings.

These are metadata versions, not immutable content snapshots: SFTP v3 typically
offers second-resolution size/mtime checks, and concurrent changes after the
worker's last check retain the filesystem's existing read semantics. Portable
export of these selected versions currently fails explicitly because relocation
requires a separate verified input rebind. Existing legacy input/export paths are
unchanged. Actual SFTP mapping, bastion and two-node transfers remain deployment
gates; fake transport tests do not qualify them.

The final focused Windows check passed 24 tests (`storage-inputs-desktop-e.log`),
including authenticated preflight -> existing job API -> real local CSV/describe
worker completion, and HTTP 409 when the selected file changed. It also covers
post-preflight version changes, execution projection changes, strict references,
mount grants, existing input roots, explicit SFTP endpoint mapping without payload
reads, URI encoding, native RunPlan binding and the portable export gate. The six
frontend files passed 38 tests (`storage-inputs-frontend-b.log`). The wider backend
group and follow-up contract/readiness checks are recorded separately in logs
`storage-inputs-desktop-b/c/d.log`; fixture/interface and generated-schema failures
found there were corrected before the final focused check. These are local
Windows acceptance results, not actual SFTP or multi-host qualification.
