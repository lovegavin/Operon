# Backend development CLI quickstart: K03–K12

These commands describe the implemented development interfaces. They are not a
release recipe or evidence that any acceptance gate passed. Run with the project
management Python and dependencies installed. Use the same explicit workspace
for every operation. The examples below use PowerShell; replace example paths,
IDs and digests with inspected local values. Source, environment and scientific
input files must already exist where the bindings declare them.

```powershell
$workspace = (Resolve-Path './operon-project').Path
python -m operon --workspace $workspace service status
```

Plan/storage commands use the existing application service and can start that
service when absent. Compile does not execute, install an environment or submit a
job. Plan execution requires the application's existing shared host pool. These
commands do not deploy a cluster or install a remote worker.

## Compile, submit, inspect and cancel a plan

For an existing graph and its independent saved parameter map:

```powershell
python -m operon --workspace $workspace plan compile "$workspace\graph.json" --values "$workspace\values.json" --require-files --output "$workspace\plan.json"
```

For schema-v2 authoring with frozen sidecars:

```powershell
python -m operon --workspace $workspace plan compile "$workspace\project\workflow.yaml" --parameters "$workspace\project\parameters.json" --inputs "$workspace\project\inputs.json" --environments "$workspace\project\environments.json" --require-files --output "$workspace\plan.json"
```

The authoring project must be inside the application workspace. Only use
`--initial` for a deliberate first import using declared defaults. Replay uses
the frozen parameters sidecar and does not refresh saved values from defaults.
Foreign authoring environments declare their strict requirement and
generation-relative executable; execution still needs a separately materialized
generation binding. Declared native/foreign file boundaries use the shared mixed
compiler; unsupported boundary representations remain explicit compile errors.

Create `binding.json` from the compiled plan's environment references and verified
generation receipts. A minimal shape for a plan with one `runtime` environment
and no storage/input boundaries is:

```json
{
  "package_root": "source",
  "environment_store": "environments",
  "environments": {
    "runtime": {
      "generation_id": "REPLACE_WITH_VERIFIED_GENERATION_ID",
      "executable": "runtime/python/python.exe"
    }
  },
  "storage": {},
  "inputs": {}
}
```

All binding roots and input paths are workspace-relative. The executable is
relative to its generation payload and must match the prepared target. Populate
every referenced storage ID and `input:` binding; each input record carries
`representation`, `path`, actual `size_bytes`, actual `sha256` and `metadata`.
Do not invent those values or substitute an arbitrary Python installation.

```powershell
python -m operon --workspace $workspace plan submit "$workspace\plan.json" --binding "$workspace\binding.json" --request-id 'analysis-001'
python -m operon --workspace $workspace plan details 'RUN_ID_FROM_SUBMIT'
python -m operon --workspace $workspace plan cancel 'RUN_ID_FROM_SUBMIT'
```

Submission and cancel request `run` permission; compile/details request read
(`context`) permission. Details returns compact authoritative state, revision,
counts and result location. For an uncertain submit response, preserve the
original plan, bindings and request ID; follow `retry_same_request`. The adapter
does not retry automatically. Disconnecting a CLI client does not cancel an
accepted scientific run.

## Prepare an offline environment explicitly

Obtain an authenticated target-native CPython archive and an exact compatible
wheelhouse beforehand. The acceptance recipe helper expects
`assets/cpython311.tar.gz` and `assets/wheelhouse/*.whl`. It records hashes and
locks; it neither downloads nor installs. Replace the digest below with the
authenticated upstream archive digest. This example executable is for a Windows
archive with a `python/python.exe` member; other targets require their actual
layout, target names and wheels.

```powershell
python scripts/acceptance/backend_environment_recipe.py --assets "$workspace\assets" --runtime-digest 'AUTHENTICATED_SHA256' --os windows --arch x86_64 --executable runtime/python/python.exe
python -m operon.environment_store --store "$workspace\environments" prepare "$workspace\assets\recipe.json"
python -m operon.environment_store --store "$workspace\environments" verify 'GENERATION_ID_FROM_PREPARE'
```

Use the recipe requirement during compilation and the verified generation ID in
the execution/export binding. The requirement identity must match; a generation
with different dependency/runtime content is rejected. Preparation and relocation
probes execute only in the explicit preparation operation. A CPython wheelhouse
does not provide R/native executable dependencies, conda relocation, arbitrary
operator requirements or cross-platform compatibility by implication.

Actual Windows and Linux generation preparation and selected portable workflows
are recorded in `backend_k03_k12_acceptance.md`. Windows mixed-language execution
uses an explicit short physical work directory; see
`windows_foreign_runtime_paths.md`. These results do not qualify arbitrary
dependency sets, two-host deployments, Slurm or a release package.

## Export a RunPlan asynchronously

This entry is separate from legacy `workflow export --format portable`. Prepare
`export-request.json` with the following fields, omitting `plan` because the CLI
loads the explicitly selected plan file:

```json
{
  "request_id": "portable-analysis-001",
  "source_root": "source",
  "environment_store": "environments",
  "output": "exports/portable-analysis-001",
  "implementations": {},
  "environments": {
    "runtime": {
      "generation_id": "REPLACE_WITH_VERIFIED_GENERATION_ID",
      "executable": "runtime/python/python.exe"
    }
  },
  "extra_files": {},
  "management_environment": "runtime",
  "input_bindings": {},
  "input_formats": {}
}
```

This minimal manifest fits only a plan that requires no external implementation
or input manifests. Native operators need their frozen `implementation` records
and explicit file maps; each destination-relative file entry has source-relative
`path`, actual `sha256`, and `role`. The selected source root must contain the
shared export kernel source. Add all declared operator scripts/resources and all
required input bindings. Source roots, environment store, input files and output
are confined within the workspace. Output must be empty. Native inferred input
paths require explicit confined overrides. Missing resources fail the build.

```powershell
python -m operon --workspace $workspace plan export "$workspace\plan.json" --request "$workspace\export-request.json"
python -m operon --workspace $workspace plan export-status 'EXPORT_RECEIPT_ID'
python -m operon --workspace $workspace plan export-lookup 'portable-analysis-001'
python -m operon --workspace $workspace plan export-cancel 'EXPORT_RECEIPT_ID'
```

Submission returns a durable receipt immediately. There is one active build and
at most four waiting builds per profile. Poll status; `complete` includes the
existing builder's verified completion receipt and bundle identity. Lookup by
original request ID handles a lost submit response. Reusing the key with changed
content fails. Queued cancellation removes the item; active cancellation is
cooperative. If the owner crashes, unfinished claims become `unknown` and require
inspection; they are never automatically rebuilt. There is no force-retry or
claim-resolution command in this slice. Build/cancel require `run`; status/lookup
require `context`.

The current builder records scientific input bindings; this interface does not
yet expose an input-copy policy. A completed build is not evidence that external
input paths remain usable on a disconnected second machine. Target-native
relocation, offline execution, resource completeness and scientific parity remain
separate acceptance checks.

For a built package with prefix-fixup scientific environments, the exporter now
includes packed offline redeployment inputs. Run `run.cmd --prepare-only` on
Windows or `sh run.sh --prepare-only` on Linux in the destination package before
scientific execution; this prepares destination bindings without starting the
workflow. The management Python must itself be directly relocatable. This
capability still requires real destination/conda acceptance, and does not download
dependencies or repair missing resources.

## Browse explicitly mounted storage

Configure `<data-dir>/storage-mounts.json` before starting the application. The
default data directory is `<workspace>/.studio`. For example:

```json
{
  "format": "operon.storage-mounts",
  "schema_version": 1,
  "mounts": [
    {
      "kind": "local",
      "storage_id": "research-data",
      "root": "/replace/with/your/authorized/data/root",
      "principals": ["profile-owner"]
    }
  ]
}
```

`profile-owner` means the authenticated local account/profile. Agent names do not
grant access. No mount file means no implicitly browsable user roots. SFTP mounts
may use an explicit SSH jump profile, existing known-host approval and credentials
provided separately; browse never provisions compute or invokes a shell proxy.

```powershell
python -m operon --workspace $workspace storage status
python -m operon --workspace $workspace storage browse research-data . --page-size 200 --pages 3
python -m operon --workspace $workspace storage stat research-data samples/data.tsv
python -m operon --workspace $workspace storage preview research-data samples/data.tsv --bytes 65536 --rows 100
```

Browse uses bounded filesystem order: default 200 entries, maximum 1,000 per
page. CLI reads up to 20 pages in one connection and closes the cursor before
exit. A partial listing explicitly requests restart; it does not return a cursor
that can be reused across CLI invocations. Direct API cursors are scoped and
expire after 30 idle seconds by default. Directory changes/expiry require
restart. Preview defaults to 64 KiB/100 rows and permits at most 1 MiB. The local
or SFTP root remains the symlink confinement boundary.

## Deployment and remaining acceptance gates

| Area | Gate still requiring direct evidence or integration |
| --- | --- |
| K03 environments | Selected Windows/Linux generations passed; arbitrary dependency/toolchain closure and existing mutable-preparation migration remain separate |
| K04 invocation | Real Windows Python/R/C branch/join passed; arbitrary ABI combinations and target-native R dependency resolution remain separate |
| K05 export | Selected moved Windows/Linux packages passed; copied-input policy and actual conda relocation remain separate |
| K06 authoring | Frozen replay/round-trip/negative group passed; unsupported semantic boundaries remain explicit errors |
| K07 storage | Real storage-only SFTP and bastion, large-directory cancellation, shared visibility and transfer binding; no silent desktop relay |
| K08 controller | Actual PostgreSQL 17 repository tests passed; controller plus remote-host failover/load gate remains open |
| K09 hosts | Two compute hosts and lost-response/disconnect/restart evidence; one available Linux host cannot satisfy this gate |
| K10 Slurm | Actual scheduler pending/run/cancel/accounting reconciliation; no real site established by these adapters |
| K11 product | Grouped API/CLI/MCP tests, full result-viewing flow and scientific parity; compact result locations alone are insufficient |
| K12 delivery | Exact Windows Setup/Linux packages, required platform gates and separate publication authorization |

Use the consolidated verification report for current evidence, rather than
interpreting these examples as passed tests. Arbitrary full native routes are
not claimed offline-complete. Further implementation notes:
`backend_k07.md`, `backend_k11_plans.md`, `backend_k11_plan_exports.md`, and the
normative `backend_implementation_contract.md`.
