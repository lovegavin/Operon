# Immutable environments and portable execution

This describes the implementation on the backend development branch. Acceptance
is recorded separately; this document is not a statement that all platforms or
all installed operators have passed.

## Environment preparation

`operon.environment_store` owns blobs, preparation journals, immutable
generations, references and process-bound leases. The environment identity binds
the target, exact dependency artifacts, builder recipe and complete file inventory.
Preparation builds in staging, checks imports/tools, checks a separate relocated
deployment, then publishes a generation atomically. A partial directory is never
treated as ready. Restart recovery reconciles a lost publication acknowledgement.

The `locked-archives-v1` builder accepts explicitly hashed Python, R or native
runtime archives. The `cpython-wheelhouse-v1` builder installs exact hashed wheels
into a relocatable interpreter, offline, using `--no-index --require-hashes`.
It does not copy the developer's venv or install into system Python. Initial
dependency resolution/acquisition is a separate explicit operation. A requirements
list without materialized artifacts is insufficient for an offline bundle.

Prefix-dependent environments retain their original packed blobs. A new target
directory is extracted and fixed up from those blobs, verified and published;
an active generation is never patched in place. The management Python must be
directly relocatable so it can prepare other runtime bindings offline. Actual R,
conda-pack and native-tool target qualification is still required.

A lease is durable before spawning. Garbage collection requires both no references
and no active/uncertain leases. Windows uses a Job Object attached before the first
worker instruction; Linux uses a subreaper whose ECHILD proof includes double-fork
and setsid descendants. A lost owner/proof is recovery-required, not evidence that
the environment or RAM can be released. Windows restart cannot reconstruct an
unnamed Job handle and therefore fails closed unless an exit proof already exists.

## Execution boundary

RunPlanExecutor consumes existing Coordinator grants and ProcessSupervisor
receipts. It is not another allocator. Native units use the existing Context,
memory manager, spill, logs and result export. Foreign processes reserve their
declared process memory and CPU; managed spill does not control an arbitrary R,
C/C++ or Python heap. OS hard limits are distinct platform capabilities.

Parameters, inputs, output declarations and invocation identity are attempt-local
JSON. Arguments are literal tokens or typed references, never generated shell
interpolation. Python/R scripts are code-hash-bound. NPY and Form boundaries use
memory mapping; JSON metadata is bounded; file/table references are streamed for
hash verification. Form verification includes all attachment files. Shape or
scientific meaning changes require explicit operators.

Collection requires exit status and process-tree evidence, then verifies outputs.
Published output manifests and artifact references are immutable. Recovered workers
read their original prepared invocation, rather than regenerating it from current
defaults. A changed default does not mutate exported parameter values.

## Portable build and run

The explicit RunPlan export API is separate from the historical graph portable
exporter. It collects a kernel dependency manifest, selected implementation
manifests, explicitly declared resources, hash-bound scripts and verified runtime
generations. Dynamic resources and external licensed tools/model weights must be
declared; missing coverage blocks completion. It performs an actual moved-package
preparation/check before publishing its receipt.

`run.cmd` and `run.sh` start the included Python and the same coordinator/worker
kernel. `inputs.json` maps external inputs; scientific data is not copied implicitly.
`parameters.json` is independently editable. Changes produce a new frozen plan
identity. `--check` verifies bindings and may report `preparation_required`;
`--prepare-only` performs local offline deployment without scientific execution.
`--work-dir`, `--output-dir`, `--memory`, `--threads` and `--resume` are explicit.
The payload cannot be used as a mutable work/results directory.

Resume uses the exact plan/input/environment identity. A completed run is reused
only after artifact revalidation. A failed/cancelled run creates new lineage;
successful ancestor-closed units may be attached after process, lease and artifact
proof checks. Their old outputs remain referenced. Terminal runs are not reset,
unknown attempts are not blindly relaunched, and this does not declare generic
cross-run scientific cache eligibility.

## Remaining qualification

An actual Windows CPython/wheel preparation has been exercised. Grouped unit,
product and real portable execution evidence is recorded in the acceptance report.
Real Linux process containment, R/native scientific parity, PostgreSQL deployment,
two-node SSH scheduling, Slurm accounting and desktop Setup remain independent
gates. A single available server cannot prove two-node failover or Slurm behavior.
