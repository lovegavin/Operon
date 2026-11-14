# Resource Download Interface and Frontend Requirements

Status: proposed interface contract. Library-side only; no application changes in this workstream.

Target: operator library `0.1.3` (interface stub and metadata), future Operon Studio application release.

## 1. Why this document exists

Large model weights and databases are currently the main reason why otherwise valid
operators cannot run. The library already declares what each operator needs in
`library/seed/src/task/step/steps/resources.json` and can check whether those files
exist through the zero-input `resource_preflight` operator, but it cannot download
anything.

The application cannot be changed right now. This document therefore fixes three
things before any code is written:

1. the library-side download interface, so the capability can be called through the
   existing MCP tools without application changes;
2. the metadata contract for downloadable files;
3. the exact frontend requirements for the later application release, so the UI is
   designed once and does not depend on ad-hoc shell commands.

This document is the source of truth for the frontend work. Update it when the
contract changes.

## 2. Current state

| Capability | Available today | MCP-callable |
|---|---|---|
| List installed operator libraries | yes | `operon_library_list` |
| List isolated environments | yes | `operon_environments` |
| Prepare an isolated environment | yes | `operon_environments_prepare` |
| Check a large resource | yes | `operon_submit` with `resource_preflight` |
| Download a large resource | **no** | **no** |
| Convert mmCIF Form to canonical PDB Form | yes, library 0.1.2 | `operon_submit` with `structure_convert_format` |
| Run an operator needing weights | only when weights already exist | `operon_submit` |

`resources.json` currently contains repository URLs, download pages and shell install
text. None of those is a file download protocol. `resources.json.install` is for a
human operator, not for the application.

The current server (verified 2026-11-14) runs Studio 5.1.17 with operator library
`main-v0.1.2` plus `fork1-v0.0.0`; `structure_convert_format` is present.

## 3. Design principles

- **Library owns the resource catalogue.** The application must not hard-code model
  names, URLs or file layouts.
- **No arbitrary URLs from the UI.** The frontend selects a resource id from the
  catalogue; only the library manifest supplies URLs.
- **HTTPS only.** `http:`, `file:`, `ftp:`, `ssh:`, `git+ssh:` and absolute local
  paths are rejected.
- **Paths stay inside the resource root.** Reject `..`, absolute paths and symlinks
  that escape the root.
- **Verify before publishing a file into place.** Download to `<name>.part`, verify
  size and sha256 when provided, then atomically rename.
- **A download is a durable job.** It must survive closing the panel, closing the
  browser tab, and reconnecting to the desktop app.
- **One writer per resource.** Concurrent downloads of the same resource either
  share one job or are rejected; never write the same target twice.
- **Torch stays CUDA.** This interface does not offer CPU/GPU variants. ESMFold and
  ESM3 keep the CUDA `torch` wheels the user requested.

## 4. Library interface

### 4.1 Manifest extension

`resources.json` entries may add a `downloads` array:

```json
{
  "id": "esmfold",
  "title": "ESMFold",
  "files": ["esmfold_3B_v1.pt"],
  "env": "OPERON_ESMFOLD_WEIGHTS",
  "url": "https://dl.fbaipublicfiles.com/fair-esm/models/esmfold_3B_v1.pt",
  "downloads": [
    {
      "url": "https://dl.fbaipublicfiles.com/fair-esm/models/esmfold_3B_v1.pt",
      "path": "esmfold_3B_v1.pt",
      "sha256": "<sha256 of the published file>",
      "bytes": 0,
      "license": "MIT",
      "requires_token": false
    }
  ]
}
```

Fields:

| Field | Required | Meaning |
|---|---|---|
| `url` | yes | HTTPS URL of one file |
| `path` | yes | Relative destination under the resource root |
| `sha256` | recommended | Expected lowercase hex digest; if absent the UI must show “unverified” |
| `bytes` | recommended | Expected size, used for progress and disk checks |
| `license` | optional | Human-readable license identifier |
| `requires_token` | optional | True for gated resources (for example ESM3) |
| `token_env` | optional | Environment variable or secret name, never a token value |

Rules:

- `downloads` is additive; existing entries without it remain check-only.
- A resource with `downloads` must still list the same files in `files`, so
  `resource_preflight` and `resource_fetch` agree.
- No wildcard URLs; one entry describes one file.
- Repository-style resources (`proteinmpnn`, `ligandmpnn`, `colabfold`,
  `alphafold2`) are **not** downloaded by this interface; they need a separate
  checkout workflow.
- Database bundles (`pfam`, `rfam`, `amrfinder`, `antismash`) need archive/extraction
  semantics; do not pretend a `.gz` file is the final database until an extraction
  step is specified.
- `esm3` is gated. A download without a user-provided token must fail with a clear
  “token required” state, not a network error.
- `boltz` uses a HuggingFace repository, not one static file. Add explicit
  `downloads` entries only after the exact file URLs and license are verified.
- `rfdiffusion` weights need the official checkpoint URL; the GitHub repository URL
  is not a weight file.
- `openfold` currently has no `resources.json` entry. Add one before advertising it.

### 4.2 `resource_fetch` operator

A zero-input operator, so it can be submitted through the existing MCP
`operon_submit` tool without any application change.

Definition:

```json
{
  "id": "resource_fetch",
  "kind": "operator",
  "inputs_arity": 0,
  "outputs": [],
  "output_parameter": "output",
  "contracts": {
    "version": 1,
    "inputs": [],
    "output": {
      "mode": "declare",
      "schema": {"ndim": 2, "numeric": true, "info_open": true, "axis_info_open": true}
    }
  },
  "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"}
}
```

Parameters:

```json
{
  "resource": "esmfold",
  "root": null,
  "overwrite": false
}
```

Behavior:

1. Resolve the resource entry and its `downloads` list.
2. If `downloads` is empty, raise `StepError` with the human install instruction.
3. Create the resource root if needed.
4. For each download:
   - skip when the destination exists, its size matches and its sha256 matches;
   - reject unsafe paths;
   - stream to `<path>.part` with a timeout and a size cap;
   - verify `bytes` and `sha256` when provided;
   - atomically replace `<path>`;
   - append a receipt entry.
5. Write `<root>/receipt.json` with resource id, timestamp, URL, bytes, sha256 and
   result.
6. Emit a Form with dims `["file", "statistic"]` and statistics
   `["downloaded", "bytes"]`; `info` includes `resource`, `root`, `n_files`,
   `n_downloaded`, `n_failed`, `status`.
7. On failure, keep `.part` and the receipt error; do not delete evidence.

The operator must not allocate a buffer proportional to the file. Stream in chunks.

### 4.3 Existing `resource_preflight`

No behavior change is required. `resource_fetch` must produce files that
`resource_preflight` reports as present, so the two operators share `files` and
`resolve_root()`.

### 4.4 MCP-only operating procedure

Until the application UI exists, a user or agent can run:

```text
operon_operator_search("resource_fetch")
operon_operator_describe(["resource_fetch"])
operon_submit({
  "base_dir": "resources",
  "nodes": [{"id": "fetch", "kind": "operator", "operator": "resource_fetch", "title": "Fetch weights"}],
  "edges": []
})
operon_job(job_id, wait_seconds=120)
operon_logs(job_id)
operon_submit(resource_preflight graph)
```

`operon_job` may time out while the download continues; the job is still running.
Poll `operon_job` again. Large files must not be downloaded through a single MCP
request with a short timeout.

## 5. Frontend requirements

These are requirements for the next application release. They are deliberately
independent of the current library build.

### 5.1 Resource inventory

Add a “Resources” section, either a new panel or a tab in the existing environment
panel. For every resource in `resources.json`, show:

- resource id and title;
- used-by operators (from the installed library);
- expected files with per-file size;
- total expected size;
- current status: `unknown`, `missing`, `partial`, `downloading`, `verifying`,
  `ready`, `failed`, `blocked`;
- verification state: `verified` (sha256 present), `unverified` (no sha256),
  `mismatch`;
- license and whether a token is required;
- last error, if any;
- action buttons.

Status must come from the backend, not from guessing on the client.

### 5.2 Actions

- **Download** (enabled only when the manifest has `downloads`).
- **Cancel** (only while a job is running).
- **Retry** (after failed/cancelled).
- **Verify** (re-hash existing files without downloading).
- **Open folder** (desktop only, local target).
- **Copy log**.
- **Bulk download** for all missing downloadable resources.

Repository/database resources without `downloads` must not show a fake Download
button. Show “Manual installation required” and the install text instead.

### 5.3 Progress

For each active job show:

- phase: `queued`, `resolving`, `downloading`, `verifying`, `extracting`,
  `completed`, `failed`, `cancelled`;
- bytes downloaded / expected bytes;
- percent;
- current speed;
- ETA (only after enough samples);
- current file name;
- job id.

Update at least every 2 seconds. Do not use a spinner-only state.

Progress must survive:

- closing and reopening the panel;
- switching tabs;
- app restart (job status reloaded from disk);
- reconnecting the remote profile.

### 5.4 Target selection

The user must choose **Local** or a connected **Server profile** before download.

- Local writes under the local installation’s resource root.
- Remote writes on the server and uses the server’s disk.
- Show free disk space and refuse to start when expected bytes exceed free space
  (unless the user explicitly overrides).
- The target must be visible in the confirmation and in the job card.

### 5.5 Gated resources and licenses

- Before downloading a `license` resource, show the license name and a checkbox
  “I accept the license”.
- For `requires_token`, ask for a token or show “Token configured/Not configured”.
  Never render the token back to the browser; store it in the backend secret store.
- ESM3 must show “Gated model: HuggingFace token required”, not a generic HTTP 401.
- Do not send tokens to the resource host from the browser; the backend performs
  the authenticated request.

### 5.6 Errors

Each failed job must display:

- HTTP status and short reason (403, 404, 429, 5xx, timeout);
- the failing URL host and file name (never the token);
- checksum mismatch details: expected vs actual;
- disk-full message;
- “gated, token required” when applicable;
- Retry and Copy log buttons.

Do not collapse all failures into “Download failed”.

### 5.7 Concurrency and queueing

- One active job per resource.
- Global limit of two active downloads by default.
- Starting a duplicate download focuses the existing job instead of creating another.
- Cancel must stop the transfer promptly and leave a resumable `.part` when possible.
- A second click during `downloading` must not create a second writer.

### 5.8 Security and validation

- The frontend never accepts a URL, path or header from the user for a resource.
- Only resource ids from the installed library are accepted.
- The backend validates `path` containment and rejects symlinks.
- The backend validates `sha256` before moving a file into place.
- The UI must display “unverified” for entries without a sha256; it must not imply
  integrity.
- No download may write into the workspace or the operator library directories.

### 5.9 Accessibility and i18n

- All states and errors have Chinese and English strings.
- Progress has an accessible label (`aria-valuenow`, `aria-valuemin`,
  `aria-valuemax`).
- Buttons are keyboard reachable and disabled states are explained.

## 6. Future application API contract

The application team may implement this interface; the library only depends on the
manifest and the operator job.

```text
GET  /api/resources?target=local|<profile>
GET  /api/resources/{id}?target=...
POST /api/resources/{id}/download
     {"target": "local", "profile": null, "overwrite": false, "accept_license": true}
POST /api/resources/{id}/cancel
POST /api/resources/{id}/verify
GET  /api/resources/{id}/status
GET  /api/resources/{id}/log
```

Download response:

```json
{"resource": "esmfold", "job_id": "res-...", "status": "queued", "target": "local"}
```

Status response:

```json
{
  "resource": "esmfold",
  "status": "downloading",
  "phase": "downloading",
  "bytes_done": 123456789,
  "bytes_total": 2500000000,
  "percent": 4.9,
  "speed_bps": 5242880,
  "file": "esmfold_3B_v1.pt",
  "error": null,
  "job_id": "res-..."
}
```

The HTTP layer should be a thin adapter over the same job service; do not implement
downloads in the HTTP handler.

## 7. Future MCP tools

If the application later exposes resource management, add:

```text
operon_resources(target=...)
operon_resource_download(resource, target=..., overwrite=false, accept_license=false)
operon_resource_cancel(resource, target=...)
operon_resource_status(resource, target=...)
operon_resource_log(resource, target=...)
```

Until then, `operon_submit(resource_fetch)` is the supported MCP path.

## 8. Resource matrix

| Resource | Direct download | Notes |
|---|---|---|
| `esm2` | yes, single `.pt` | public URL |
| `esm_if1` | yes, single `.pt` | public URL |
| `esmfold` | yes, single `.pt` | 2.5 GB checkpoint; CUDA torch remains |
| `antifold` | yes, single `.pt` | URL in `environments.json` |
| `rfdiffusion` | no, needs official checkpoint URL | GitHub repo URL is not a weight |
| `boltz` | no, HuggingFace repo | needs per-file URLs and license review |
| `openfold` | no entry yet | add manifest entry first |
| `esm3` | no, gated | HuggingFace token required |
| `proteinmpnn` | no | repository checkout |
| `ligandmpnn` | no | repository checkout |
| `colabfold` | no | repository/install |
| `alphafold2` | no | repository + params layout |
| `prodigal` | no | executable |
| `pfam` | no | `.hmm.gz` archive + extraction |
| `rfam` | no | `.cm.gz` archive + extraction |
| `amrfinder` | no | multi-file database directory |
| `antismash` | no | multi-file database directory |

Only the first four are candidates for the first `downloads` implementation. The
rest need a separate contract and must not be advertised as one-click downloads.

## 9. Acceptance criteria

The frontend work is accepted when:

1. all 14 resources appear with a truthful status and no invented files;
2. a resource with `downloads` can be downloaded from the UI and from MCP;
3. a 2 GB download survives closing the panel and reconnecting;
4. progress reports bytes, percent, speed and phase;
5. cancel stops the transfer and leaves a retryable state;
6. checksum mismatch is reported and does not replace the old file;
7. target selection writes to the correct local or server root;
8. gated resources show a token/license flow and never print the token;
9. unsafe paths and arbitrary URLs are rejected;
10. a resource without `downloads` has no Download button.

## 10. Out of scope

- Changing Boltz `CXXABI_1.3.9`; this needs the application to set
  `LD_LIBRARY_PATH` for the dependency worker.
- Switching ESMFold/ESM3 to CPU torch; the user requires CUDA.
- Downloading repository checkouts automatically; this needs its own design.
- Downloading from arbitrary user-provided URLs.
- Replacing `resource_preflight`; it remains the verification primitive.
