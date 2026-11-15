# K06 authoring v2 implementation

Status: implementation and focused tests written; **tests have not been run in
this development phase**. Consolidated testing is required before acceptance.
This is a bounded authoring increment, not completion of every K06 service/API
operation or of the K04 execution gate.

| Boundary | Implemented behavior | Module tests | Product integration | Real E2E | Remaining work |
| --- | --- | --- | --- | --- | --- |
| YAML v2 | Strict Pydantic 2 models, established SafeLoader safeguards, bounded parsing, typed static references | Written, not run | Integration hooks available | Not run | Consolidated suite and adapter integration |
| Save/replay | Existing recursive graph/workflow parameter snapshots, independent input JSON, no default extraction during replay | Written, not run | Shared `freeze_defaults=False` propagation implemented | Not run | Verify native operator and Reader default drift tests |
| Compatibility | Canvas/v1 import, explicit old task import, canonical v2 export, requested lossless v1 export | Written, not run | Existing graph model/compiler retained | Not run | Existing legacy/route/converter regression suites |
| Profiles | CLI fields override one profile, which overrides workflow defaults; binary bytes and integer seconds | Written, not run | Explicit target, environment, memory and CPU lowering for invocation plans | Not run | Time limits and storage profile enforcement |
| Foreign invocation | Python/R snapshots and command argument tokens lower to existing RunPlan/UnitSpec | Written, not run | Shared compiler facade and invocation adapters | Not run | Real language/runtime and portable export acceptance |
| Mixed native/foreign | Explicit Form `.bpform` boundaries join compiler-produced native subgraphs and foreign units | Written, not run | Existing route/compiler, exchange protocol and unit DAG validator | Not run | Materialization/runtime E2E; additional proven codecs |

## Files and service hooks

`operon/planning/authoring_v2.py` is a metadata normalizer. It does not own a DAG
executor, route expansion, converter selection, memory manager, or scheduler.

- `parse(text)` retains the existing `WorkflowLoader` duplicate-key, tag, alias,
  and YAML 1.2 boolean policy. The subclass adds construction limits: 10 MiB of
  UTF-8 YAML, depth 48 and 50,000 constructed items. Sidecar JSON receives byte,
  structure, duplicate-key and finite-number checks. Limits reject; they never
  truncate content.
- `normalize(value, directory, *, parameters=None, inputs=None,
  environments=None, profile=None, overrides=None, initial=False, catalog=None,
  ui=None)` returns `NormalizedWorkflow`, `NormalizedForeignWorkflow`, or
  `NormalizedMixedWorkflow`. Text is parsed safely; mappings may be
  v2 authoring, canvas graph JSON, or v1 workflow YAML. Sidecar mappings can be
  supplied by the application after its own authorized resource loading.
- `load_workflow(path, **options)` loads the YAML and contained JSON sidecars.
  Optional adjacent `ui.json` restores both top-level and nested route positions.
- `NormalizedWorkflow.spec` is the existing immutable `WorkflowSpec`;
  `.parameters` is the deeply immutable `operon.graph-parameters` snapshot;
  `.inputs`, `.environments` and `.profile` expose the other resolved metadata.
- `WorkflowCompiler.compile_authoring(normalized, catalog=None, *, root=None,
  require_files=False)` is the common facade. Each normalized result's
  `.compile(...)` delegates to it. Native graphs use `compile(...,
  freeze_defaults=False)`; foreign/mixed lowering produces the existing
  invocation records. The default root is the normalized workflow directory.
- `export_mapping(workflow, directory)` returns the canonical YAML mapping and
  JSON sidecars without filesystem changes. `export_workflow(workflow,
  directory, legacy=False)` writes a new empty destination using exclusive
  creation and never replaces an existing parameter file. It does not read
  current catalog defaults. `legacy=True` invokes the existing v1 exporter only
  if v2 execution metadata can be represented without dropping it.
- `json_schema()` derives the public authoring schema from the same strict
  models. This schema is distinct from the existing K01 graph `WorkflowSpec`
  schema, despite both carrying an explicit version 2.

The compiler hook must reach the existing `compile_legacy` / `compile_graph`
route, including recursive route expansion and Reader parameter validation.
Skipping only the outer compiler's `freeze_spec` is insufficient because the
existing inner graph compiler also freezes defaults. Existing callers retain
their compatibility default (`freeze_defaults=True`).

CLI/API/MCP should call these hooks through the application service. They must
not invent separate normalization, expression evaluation, graph execution or
default-replacement behavior. The adapter supplies request IDs and retry
metadata; normalization errors use `ContractError` with `code`, `message`,
`details.path`, optional `details.errors`, and `next_actions`.

## Canonical vocabulary and value lifetime

Only these top-level fields are accepted: `format`, `schema_version`,
`params_file`, `inputs_file`, `environments_file`, `processes`, `workflow`,
`profiles`. `format` is `operon.workflow` and `schema_version` is integer 2.

Processes use `runner`, exactly one of `operator` / `route` / `script` /
`command`, `input`, `output`, `environment`, `resources`, and initial
`parameters`. Named ports declare `type` (`form`, `path`, `val`, `tuple`),
optional `format`, existing graph `handle`, and optional `contract` metadata.
Actual scientific port compatibility and converter selection remain the shared
graph compiler's responsibility. Boundary type mismatches are rejected before
normalization. Named declarations, including unused output declarations, are
retained in v2 export.

`workflow` contains `take`, `steps`, and `emit`. Its explicit compatibility fields
are `name`, `defaults`, `memory`, `runtime`, `manifest_extra`, `plugin_lock`, and
`interface`; these preserve existing graphs rather than silently flattening
routes or losing memory and execution settings. Each step has `process`, `in`,
initial `params`, initial `context_params`, `title`, and optional `input_count`.
The `workflow` node name is reserved for input references. Dotted node names
remain supported; an ambiguous dotted node/port reference is an error.

Data bindings use `{ref: workflow.matrix}` / `{ref: step.result}` or
`{input: matrix}`. Bindings may retain the existing edge `id` and `adaptation`
contract. Parameter/source-value expressions use `{param: name}` and
`{input: name}`. These select exact JSON values; they do not stringify values,
interpolate strings, evaluate code, or recursively evaluate the selected value.
`${...}` expressions in value positions fail explicitly.

The following is a synthetic authoring example; `example_transform` and
`ExampleReader` are illustrative registered names, not bundled dependencies:

```yaml
format: operon.workflow
schema_version: 2
params_file: parameters.json
inputs_file: inputs.json
processes:
  Transform:
    runner: native
    operator: example_transform
    input:
      matrix: {type: form, handle: in-0}
    output:
      result: {type: form, handle: out}
    parameters: {threshold: 2}
workflow:
  take:
    matrix:
      type: form
      source: {reader: ExampleReader, path: {input: matrix}}
  steps:
    transform:
      process: Transform
      in: {matrix: {ref: workflow.matrix}}
      params: {threshold: {param: threshold}}
  emit: {result: {ref: transform.result}}
profiles:
  local: {executor: local}
```

For explicit initial import, input JSON can be `{"matrix":"data.fixture"}`
and parameter JSON `{"params":{"threshold":0}}`. Calling `initial=True` with
a catalog extracts declared defaults exactly once, preserving supplied zero,
false, null and empty collections. Canonical export removes inline step values
and writes the existing recursive `operon.graph-parameters` format. Its `params`
field stores workflow globals, and `nodes` stores Reader args, step/context
values and nested route values. Replay requires that complete snapshot and does
not reconstruct missing nodes from defaults. `_input_names` is rejected in both
initial and replayed step values.

The canonical export may assign a process definition per stable step ID; that
does not create additional execution nodes. Source data paths are retained in
`inputs.json`; local paths remain resolved to the original input location.
Remote paths retain their server namespace. UI coordinates live in `ui.json`;
nested legacy graph snapshots contain only required zero position placeholders.
Sidecar paths must be contained relative paths even if the caller injects data
instead of reading those files.

## Profiles and explicit unsupported boundaries

Profiles contain only `executor`, `target`, `resources`, and `storage`. One
selected profile is supported. Its fields override workflow defaults; explicit
CLI override fields override the selected profile. Nested target/resource/
storage dictionaries merge by field. `cpus` is a positive integer; `memory`
accepts positive integer bytes or `B`, `KiB`, `MiB`, `GiB`, `TiB`; `time` accepts
positive integer seconds or `s`, `m`, `h`, `d`. Booleans and numeric strings with
no units are rejected.

Policies are normalized and preserved for integration. Native-only authoring
can bind a fused native group to one exact declared CPython environment and one
resource policy. Different environment requirements or per-process resource
policies require a split at explicit materialized boundaries. The selected
executor/target and positive process reservation are applied to the native unit;
managed memory remains separate. Timeouts and storage defaults remain explicit
unsupported boundaries. Legacy native graphs without environment declarations
retain their existing local compatibility path.

Command argv is an array of explicit typed tokens: `{literal: text}`,
`{input: port}`, `{output: port}`, `{param: name}`, `{resource: resource_id}`.
Bare strings and shell expressions are not a command grammar. This array
contains arguments only; the immutable environment declaration selects the
executable. Empty arrays are valid. No command is launched by import or lint.
The module does not parse arbitrary `.nf` or claim Nextflow DSL compatibility.

## Shared invocation and mixed materialization lowering

`operon/planning/invocation_lowering.py` implements static lowering, not a
scheduler. The existing `execution.unit_executor.unit_dependencies` validates
the final combined DAG. All-foreign workflows carry `operon.frozen-parameters`;
mixed workflows carry the established `operon.workflow-parameters` shape:
workflow globals, Reader `sources.<id>.args`, and `steps.<id>.params`,
`context_params`, plus recursive `route` snapshots where applicable. Replay
requires exact node coverage and never consults current defaults. Selected
profile/override values become exported workflow defaults.

Environment JSON maps a process environment name to
`{requirement: <strict EnvironmentRequirement JSON>, executable: <relative path>}`.
The executable path is inside the immutable environment generation, with no
PATH lookup. Each used environment's exact requirement hash is recorded in
`execution_policy.environment_refs`. Every invocation requires an explicit
executor and positive full-process memory/CPU declarations, with process values
overriding profile resources. Native invocation environments must be CPython.
Foreign managed-memory budget is zero; native managed budgets, spill settings,
and process reservations remain distinct and are validated for consistency.

Foreign process ports support explicit paths and `type: form, format: bpform`.
Script declarations must agree with these named ports and file formats. Script
content is validated and hash-bound inline, with a stable package resource path
`scripts/<hash-prefix>/<filename>` in `CodeRef` and `payload.script_resource`.
The exporter materializes that declared resource; planning writes no scripts.
Script argv uses `--in-<port>` and `--out-<port>`, with parameter values delivered
through the existing invocation parameter JSON. Compound/null values cannot be
coerced into command argv.

A foreign Form result occupies `<port>/value.bpform`, a dedicated directory for
the envelope and sibling attachments; its output representation is `form`.
The script must author a valid existing ExchangeWire envelope. The planner does
not interpret CSV or arbitrary arrays as Forms. Native/foreign edges require
explicit `form/bpform` declarations on both sides. A native raw-file workflow
input requires a selected Reader. In this increment each native process or
route is a compiler-produced subgraph; native routes and their converters remain
fused internally. Cross-process native edges in a mixed workflow also require
explicit materialization declarations. Native-only workflows keep their
existing fused graph compilation.

Native subgraph inputs use named task sources, `runtime.exchange_inputs` and
author-declared `exchange_contracts`. Native outputs are resolved by the shared
graph/route compiler and exported with `exchange_outputs` and public
`exchange_aliases`. Metadata must prove that each published native result is a
Form. `UnitSpec.input_bindings` uses `input:<workflow-input>` or
`artifact:<producer-unit>/<port>`; explicit bindings replace source locations
before invocation. Plan execution policy records external input locations and
representations for the portable exporter to lift into deployment bindings.
No placeholder scientific operator, implicit converter, or second DAG executor
is inserted.

Current explicit gaps: mixed raw-file/FileArtifact native outputs, non-Form
native exchange codecs, graph-wide retention across separately materialized
native units, arbitrary mixed `manifest_extra`/graph interfaces, time limits,
and storage profile settings. These return concrete errors rather than losing
their semantics. Legacy YAML export rejects foreign/mixed invocation plans.

Legacy graph and v1 YAML imports use a dedicated compatibility normalizer.
Older task YAML (`sources` plus a list of `steps`) requires explicit initial
import with a catalog and delegates to the existing task importer. Save its
result as v2 before replay. Requested legacy export fails when profiles,
environment references or process resources cannot be retained.

## Verification to run in the consolidated stage

Native invocation bootstrap now carries projected executable descriptors in
the unit payload and full original declarations in `diagnostics` for audit.
Schema defaults, presentation fields, and declaration audit hashes are excluded
from execution identity; validation structure, IO, entry points, code/package
identity, executable/resource digests, SDK ABI and origin remain bound. The
worker compares the original declarations' projection to the frozen snapshot
and uses existing SDK code verification before loading each selected class.
Only explicit code roots are searched for the named module file; no library
discovery or mutable environment proxy is used. Operators use `LazyRegistry`,
Readers use `reader_proxy`, and frozen schema validation does not inject defaults.
The existing `execute_task`, ContextBridge, memory and logging paths are retained.
The attempt-local snapshot is contained and hash-checked. Environment/isolated
descriptor policies require explicit unit environment lowering. Existing K02
JobService invocations retain their frozen plugin-lock bootstrap.

Focused files: `tests/test_workflow_authoring_v2.py` and
`tests/test_invocation_lowering_v1.py`. They cover typed values and
references, structured error paths, unchanged/new operator and Reader defaults,
same-compiler plan identity, single-profile precedence, strict resource types,
aliases/tags/duplicate keys/nonfinite values, parse limits, unknown fields,
contained sidecars, frozen snapshot completeness, nested route/edge adaptation/
memory/UI round trips, v1 compatibility, protected export destinations, argv
validation, the metadata-only import boundary, typed foreign argv, script
resource hashes, exact environments, Python/R/command branch joins, explicit
Python/R/native/Python Form boundaries, nested native route preservation, frozen
mixed replay, profile snapshots, self-loops, cycles and resource failures.
`tests/test_native_runtime_snapshot.py` additionally defines owned temporary
provider modules and exercises actual Reader/operator loading, ContextBridge
worker execution, lazy registration, default-drift identity, audit/code
mismatches, snapshot hash/path validation and native-only environment binding.
These new tests are authored but have not been run in this development phase.

Then run the existing workflow v1/import/archive, RunPlan, invocation, nested
route, converter and memory regressions with the consolidated shared compiler
changes. Record commands, interpreter/platform, pass/fail/skip counts and log
paths in the final gate report. No unit test, static normalizer or generated
archive substitutes for CLI/API/MCP interaction or real platform execution.
