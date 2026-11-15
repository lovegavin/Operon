# Independent script packages

The first verified portable target is a file-based Python script workflow with a
prepared, relocatable Python runtime. Export includes the actual runtime files,
script source, frozen parameter JSON, a readable `run.py`, platform launcher and
manifest. The independent runner imports only the standard library, never Operon
or its SDK.

```sh
operon workflow export workflow.yaml --format portable --runtime-dir ./prepared-runtime --output ./analysis-package
```

The runtime directory must contain `portable-runtime.json`:

```json
{
  "format": "operon.portable-runtime",
  "schema_version": 1,
  "platform": "win32",
  "machine": "AMD64",
  "python": "python.exe"
}
```

It must include the real interpreter, standard library, required packages, native
libraries and licenses. An arbitrary venv is rejected. Export probes the actual
interpreter, copies the runtime and probes the relocated copy; declared dependency
versions must match. It does not download packages or represent a requirements
file as a bundled environment. Target and build OS/architecture currently must
match for this verification.

Edit `INPUTS` and `OUTPUT_DIR` at the top of exported `run.py`, then run `run.cmd`
or `run.sh`. Inputs are not copied automatically. Output directories must be fresh;
existing results are preserved. Per-step logs, parameters and a run receipt are
saved beside outputs. No global PATH or system Python configuration changes occur.

Native Context/Form operators, route operators, non-Python scripts and conversions
without verified portable adapters are explicitly rejected. Scientific source
Readers also need portable adapters; export never silently omits Reader work.
The `converters/` directory is reserved for adapter implementations. Unsupported
conversion chains fail export-check rather than producing an incomplete package.
Automatic dependency solving, prebuilt environments for every platform and the
native Hi-C export adapters are not implemented by this module.

Acceptance includes a real standard-library-only Windows runtime, relocation to
a different directory, running a frozen file transformation through its bundled
interpreter and confirming Operon is not importable. This test does not establish
compatibility for every scientific dependency or Linux binary distribution.


### Relocation verification time budget

Export always hashes the delivered payload and checks it again after relocation.
The build receipt records `verification.inventory_seconds`, `entries`, and both
probe time budgets. The check budget is `max(180, ceil(60 + 4 * inventory_seconds))`
seconds; destination preparation uses `max(600, ceil(120 + 6 * inventory_seconds))`.
Each is capped at 7,200 seconds. The measured duration comes from the parent
process scanning this exact payload; subprocess output cannot extend the deadline.
This allows slower storage and cold copied runtimes without disabling hashes,
turning timeouts into success, or making probes unbounded. Cancellation still
stops an active probe. A timeout retains its failure receipt and recent progress.


### Reusable environment packages

Managed generations now seal into content-addressed TAR layers in
`packages/sha256/<digest>.tar`. `packages.json` binds the layers to the original
generation, requirement and content identities. `runtime/` is the language layer;
Python `site-packages`/`dist-packages` and explicit `packages/` are dependency
layers; remaining resources form a separate layer. Opaque native/R distributions
remain intact runtime closures unless their builder separates dependency paths.
Identical layers deduplicate across generations. Conflicting requirements retain
separate generation bindings and isolated worker processes; no imports are renamed.

Sealing an old generation performs one full audit and validates the bytes written
to each archive. Subsequent ordinary verification hashes the small number of
archive files, not the extracted tree. Package copies are verified while copying.
Exports record managed cache exclusions explicitly and still verify code, metadata,
package archives and relocated execution. A launchable management cache remains
in the standalone package, so this change does not promise a smaller download.

Expanded payloads are managed execution caches, not independently authenticated
artifacts. Direct edits to those caches are unsupported and are not detected by
normal package verification. This is not isolation from a malicious same-account
user. Use `audit` for an explicit per-file cache audit; use `materialize` into a
fresh store to recover from immutable archives without altering a live generation.
Package changes require new content identities. Existing leases and generation GC
are unchanged. Shared package blobs are retained conservatively, not removed when
one referencing generation is collected.

```sh
python -m operon.environment_store --store ./environments package GENERATION
python -m operon.environment_store --store ./environments verify GENERATION
python -m operon.environment_store --store ./environments audit GENERATION
python -m operon.environment_store --store ./environments materialize GENERATION --destination ./recovered-environments
```

Writable managed stores automatically seal an old generation on its first normal
binding. Read-only legacy portable bundles retain their original verification
behavior and are never modified in place. New exports use package bindings.
