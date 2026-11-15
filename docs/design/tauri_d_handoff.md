# Session D handoff: native OS integration

Scope implemented: `desktop-tauri/src/{navigation,dialogs,artifacts,credentials}.rs`.
No `main.rs`, `bridge.rs`, manifests, frontend, shared types, Python product or
library files were changed. The scaffold did not exist in this worktree, so the
four files were created under `desktop-tauri/src/`.

## Public APIs

### `navigation.rs`

- `allow_owned_navigation(target: &Url, origin: &Url) -> bool`
  Exact scheme/host/effective-port match, root path `/` only, no userinfo,
  query, fragment or non-HTTP(S) scheme. Main-frame/top-level predicate only.
- `is_documentation_url(url: &Url) -> bool`
  HTTPS `github.com/lovegavin/Operon` repository/subpaths only; no userinfo, no
  explicit port, no query. Fragments are allowed.
- `open_documentation(url: &Url) -> Result<(), HostError>`
- `open_default_documentation() -> Result<(), HostError>`
- `open_documentation_with(url, opener)` plus `DocumentationOpener` test seam.
- `DOCUMENTATION_BASE_URL`.

Root should expose a fixed documentation command (or the checked URL command),
not an arbitrary `openUrl` command. Tauri capabilities must separately deny
new-window/subframe privileges; the URL predicate cannot revoke them.

### `dialogs.rs`

- `SelectPathKind { OpenFile, SaveFile, Folder }`, serde `snake_case`.
- `select_path(kind) -> Result<Option<PathBuf>, HostError>` using
  `rfd::AsyncFileDialog`; cancellation and an empty selection are `Ok(None)`.
  No initial directory, filters, default name, executable or command input; no
  filesystem I/O. Returning a path is the authorization for later use.

### `artifacts.rs`

- `open_committed_artifact(origin, token, profile, run_id, artifact_id, file_id)
  -> Result<(), HostError>`.
- `open_committed_artifact_with(..., transport, opener)` for tests/root mocks.
- Traits: `ArtifactTransport`, `ArtifactDownload`, `PathOpener`.
- Types: `ArtifactFile`, `FilesPage`, `ArtifactSummary`, `ArtifactsPage`,
  `TransportError`; production `ReqwestArtifactTransport`/`ReqwestDownload`.

Flow: validate IDs, resolve artifact digest from `/api/v1/plans/{run}/artifacts`,
resolve `file_id` through the paginated `/files` endpoint (bounded at 4096
entries), validate exact name/sha256/size/media type, enforce the explicit safe
extension allowlist, reuse/rehash a cached file or stream to a `create_new`
temporary file, verify SHA-256 and size, atomically rename, verify the final
path again, then call the OS opener. Fetching uses `Authorization: Bearer`,
redirects off, proxy off, finite connect/total timeouts.

### `credentials.rs`

- `get_native_credential`, `set_native_credential`, `delete_native_credential`.
- `_with(&dyn CredentialStore, ...)` injectable variants.
- `Secret` has no `Debug`/`Display`/`Serialize`; only `expose()`.
- Service scope: `org.operon.studio.experimental/<installation_id>`; account and
  value are validated/bounded (8 KiB maximum value). Missing get is `Ok(None)`;
  missing delete is success.
- Not integrated with SSH or the renderer. No migration. Production SSH remains
  in the Python credential service.

## Root integration requirements

1. Add `mod navigation; mod dialogs; mod artifacts; mod credentials;` as
   appropriate. Root owns command registration and origin/session checks.
2. Add dependencies/features (root owns manifests):
   `url`, `serde`/`serde_json`, `sha2`, `reqwest 0.12` (needs the response
   streaming feature for `Response::chunk`; enable a TLS backend if HTTPS is
   allowed), `rfd 0.15`, `keyring 3` with `windows-native`, and `windows-sys`
   with `Win32_Foundation` + `Win32_UI_Shell`. Tests use `tokio` and `tempfile`.
3. Wire the Tauri main-window navigation handler to
   `allow_owned_navigation`; do not grant new-window/subframe privileges.
4. Pass the owned **loopback HTTP(S) origin with path `/`** to artifacts. The
   `token` parameter is sent as a Bearer token. If the host bridge uses
   `X-Studio-Token` instead, adapt `ReqwestArtifactTransport` or call the
   `_with` variant with a root-owned transport.
5. Do not expose credential functions to JS and do not add a general URL/path
   opener command.

## Deviations / decisions

- **Native association only.** The fixed design forbids renderer-selected
  executables/viewer preferences. No viewer preference config was added despite
  the older session-assignment wording.
- **Windows opener.** `ShellExecuteW` with the fixed `open` verb is used on
  Windows. Other platforms return `host_capability_unavailable`/unsupported
  rather than falling back to a shell command; root may replace this with a
  reviewed cross-platform opener.
- **Artifact digest is fetched.** The file list response does not contain the
  artifact manifest digest, so the implementation reads the artifact list once
  (bounded to 64 pages) to build `viewer-cache/<artifact digest>/...`.
- **Error mapping.** Invalid/unknown opaque IDs and missing backend refs map to
  `host_request_stale`; unsupported extensions/opener failures map to
  `host_capability_unavailable` with `use_http_artifact_link`; transport, cache
  integrity and path-safety failures map to `host_bridge_unavailable`; invalid
  service origins map to `host_unsupported`. No raw OS/server text is copied.
- **Origin validation** requires a loopback HTTP(S) origin (`127.0.0.0/8`, `::1`,
  or `localhost`) with no userinfo/query/fragment and path `/`. Root must not
  pass a production or remote server origin.

## Tests included (not run here)

- Navigation: exact origin/root, malicious hosts, userinfo, alternate ports,
  executable/opaque schemes, documentation allowlist and injected-opener
  no-call/call checks.
- Dialogs: cancellation/empty selection mapping and snake_case serialization.
  The real picker is not invoked.
- Artifacts: success path, cache reuse/rehash, corrupt cache replacement, invalid
  IDs before network, unknown refs, extension/traversal rejection, SHA/size/ETag
  mismatch cleanup, bounded pagination/entry limit, and Unix symlinked-cache
  rejection. HTTP is mocked through the injected transport; the OS opener is
  mocked through `PathOpener`.
- Credentials: injected-store round trip and namespace, missing/delete behavior,
  invalid identifiers, value bounds, redacted errors, and an opt-in real Windows
  keyring test (`OPERON_RUN_KEYRING_TEST=1`, unique account, cleanup guard).

**Not run:** `cargo build`, `cargo test`, clippy/format, an actual file picker,
an actual OS viewer, a real HTTP server, a real Windows junction/symlink, and the
real Windows keyring test. Root must resolve crate APIs/features, add the
modules, then run the focused tests.

## Constraints observed

No shell/`Command` invocation in product code, no ACL changes, no commits, no
dependency manifests, no library/Python/sharedtypes/frontend changes, and no
native path returned from the public artifact API.

## Integrated review supersedes this handoff

The root integration on experimental/tauri-shell corrected Windows venv process
ownership, exit/tree-drain proof, environment whitelisting and studio HTTP
credentials, and compiled/tested the combined implementation. This document
records the original contractor handoff, not final acceptance. Use
`tauri_native_acceptance.md` and the integrated branch for subsequent work.
