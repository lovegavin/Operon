# K11 plan result files

Plan result reads use `Application.plans`, authenticated pool operations and the
existing host StateStore. They do not create another executor or allocator.

| Operation | HTTP route after `/api/v1/plans/{run_id}` | Limits |
| --- | --- | --- |
| File metadata | `/artifacts/{artifact_id}/files` | 100 entries by default, maximum 200; response budget 32 KiB by default, maximum 64 KiB |
| Preview | `/artifacts/{artifact_id}/files/{file_id}/preview` | 16 KiB and 100 rows by default, maximum 64 KiB and 1000 rows |
| Explicit open/download | `/artifacts/{artifact_id}/files/{file_id}/open` | Selected file, streamed in 1 MiB blocks after complete SHA256 verification |

All routes require the existing `context` permission. The pool checks workspace,
principal and session ownership. Unknown/duplicate query selectors are rejected.
File IDs bind the artifact identity and committed manifest entry. Requests never
accept a filesystem path. Public file rows contain `file_id`, `name`,
`size_bytes`, `sha256` and `media_type`; no absolute paths are published.

An artifact must be committed, its owning attempt succeeded, its resource lease
released, and its receipt attempt/fence/run/digest consistent. Cross-run reuse
also requires a succeeded explicit reuse attachment and a live retention pin for
the requesting run. The bounded manifest must match its registered digest.
Unregistered neighboring files are inaccessible. Opened descriptors reject
symlinks, junctions, hardlinks, special files and path replacement; POSIX parent
descriptors or the Windows final handle retain the checked location.

Text previews return `kind`, `content`, `truncated`, `bytes_read` and
`digest_verified`. Binary content is not embedded. A partial preview intentionally
does not read the remainder or claim whole-file digest verification. A complete
preview or full download rejects a checksum mismatch. Full downloads retain the
checked descriptor until streaming completes or disconnect cleanup runs.

Downloads default to attachment. Only PNG/JPEG/GIF/WebP can opt into inline
display. SVG/HTML remain attachments. Responses use safe encoded filenames,
`nosniff`, a sandbox CSP and private/no-store caching. Desktop clients must use
authenticated fetch and render preview text as text, not HTML.

Embedded and managed-local host pools support full opening. An external remote
pool returns `artifact_transfer_required` before fetching full content. Metadata
and bounded previews remain host-side. Explicit remote plan artifact transfer and
external desktop viewer registration are not implemented by this change.

MCP adapters expose `operon_plan_artifact_files`,
`operon_plan_artifact_preview` and explicit `operon_download_plan_artifact`.
The existing workspace-confined download destination policy remains in force.

## Retained upstream result behavior

Additive ports from `387b6792`, `6e6750a7` and `42ccc61f` restore legacy job result
listing/download, the `JobService.result_file` alias and composite remote result
listing through `result_files_for(profile_id, job_id)`. They use the existing
Application artifact facade and remote output transfer. These legacy recursive
inventories are distinct from the new bounded committed-plan manifests.

## Evidence and remaining gates

Windows source checks used the project CPython environment with pytest plugin
autoload disabled. `verification/backend/plan-artifact-desktop-a.{log,xml}`
records 62 passed and 6 skipped across new result reads, existing log reads,
upstream job downloads and viewer lifetime tests. The final focused group
`plan-artifact-desktop-b.{log,xml}` records 42 passed and 4 skipped, including
reuse pins, same-size corruption, UTF-8 boundaries, managed-local handoff,
authorization and real file descriptor reads. Hardlink guards passed; Windows
symbolic-link creation was unavailable even with the approved execution context.

These are real local file/StateStore and HTTP adapter checks, not claims of a
desktop interaction, remote transfer, dual-host or Slurm acceptance. The separate
desktop acceptance fixture helper explicitly prepares a copied private runtime
with real import/relocation probes and writes source, compile and binding files;
the tester must still execute and inspect the product flow.

## Desktop acceptance companion

Run the helper with the installed private Python, selecting the same workspace
that the desktop service uses. This explicitly copies the runtime, hashes it,
executes import probes and repeats them after relocation. It does not install
packages or change the installed interpreter. A fresh fixture folder is required;
failed preparation is retained and never described as a usable generation.

```text
<private-python> -I -B <candidate>/scripts/acceptance/prepare_desktop_plan.py
  --workspace <service-workspace> --application-root <installed-code-root>
  --python-home <installed-private-python-directory> --prepare-environment
```

The command is one line when executed. Windows defaults to `python.exe`; Linux
defaults to `bin/python3`, overridable with `--python-executable`. The runtime
must include the shipped management dependencies (`psutil`, `pydantic`, `yaml`,
`jsonschema`, `numpy`, `packaging`), all verified to import from the copied prefix.
It is not a developer virtualenv. Plan computation itself uses only stdlib.
Preparation temporarily needs space for an archive, immutable builder blob,
generation and relocated probe copy. The helper does not silently delete them
after failure. The redundant source archive is removed only after success.

Under `desktop-plan-acceptance/`, import `compile-request.json`, compile it and
import `binding.json`. `execution-plan.json` is an equivalent prepared snapshot
shortcut. The two dependent stages multiply input 7 by 2 and then 3; committed
results must be 14 and 42. `export-request.json` records the matching confined
export configuration. `preparation.json` contains the actual generation/probe
receipt and `expected.json` the known synthetic result. No hashes need manual
entry. Reopening the UI must retain its original submission identity and result
history; this interaction remains a separate test-machine acceptance step.

The older development Python runtime failed its first probe in a deeply nested
Windows fixture workspace because a dependency resource exceeded normal path
handling. A fresh shorter workspace completed actual original/relocated probes
(`desktop-fixture-real-b.log`). The installed candidate runtime and its bundled
path hooks must still be qualified on the test machine; this helper does not
promise arbitrary runtime/path combinations.

The helper's focused metadata/archive tests passed 5/5 in
`desktop-plan-fixture-a.xml`. Actual execution of its prepared fixture passed
1/1 in `desktop-fixture-e2e-b.xml`: shared PlanService compilation, duplicate
same-request admission, two real dependent processes, committed values 14/42,
and artifact metadata/preview/verified download. Both attempts had matching tree
exit proofs, released resource/environment leases and no surviving matching PID
after pool shutdown. Source hashes and cleanup evidence are recorded in
`verification/backend/plan-artifact-desktop-evidence.json`.

| Unit | Implemented behavior | Module tests | Product integration | Real E2E | Remaining blockers |
| --- | --- | --- | --- | --- | --- |
| K11 result slice | Owned committed-file IDs, bounded previews, explicit local downloads, shared HTTP/MCP facade | Final read group 42 passed, 4 permission skips; companion 5 passed | Actual PlanService/PoolService result path passed | Two-stage private-Python fixture passed; 14/42 and cleanup verified | Desktop interaction and candidate package acceptance; remote full transfer; symbolic-link checks on a permitted filesystem |
