# Automatic standalone export

The canvas and standalone exporter use the same frozen RunPlan. Choose the run
environment, validate the route, and prepare/export it from the canvas. Code,
declared resources, parameter values and environment packages are collected by
the application. A hand-written file manifest is not required.

## What is included

| Selected dependency | Capture and deployment |
|---|---|
| Private CPython / venv | Private base runtime plus the selected environment's packages |
| System Python | Exact Python patch-level standalone runtime plus selected scientific packages |
| Conda Python | Original scientific prefix packed by conda-pack; separate private bootstrap |
| Named Python environment | Separate captured interpreter and package closure |
| Conflicting target packages | Separate frozen targets, retaining subprocess isolation |
| R | Private R runtime or exact-version managed system-R replacement; prepared package-library receipts |
| Declared external tools | Owning Conda prefix or self-contained private installation, including resources |

First preparation can download an exact runtime and private export tools. This
happens only during explicit preparation, never on app startup or registration.
An incomplete acquisition is not reused. Preparation errors identify unavailable
tools or versions; they do not silently substitute another Python ABI.

Conda fixups run in the final destination cache. The original packed archive
remains immutable. Moving the exported package creates a new destination binding
from that archive rather than applying conda-unpack a second time to modified
files. Runtime/package closures are deduplicated. Repeated preparation reuses
verified package receipts instead of rescanning every installed dependency file.

## Running the exported route

Unpack on a matching operating system and architecture. Edit `inputs.json` to
point at the input data; paths may be relative to the package. The package does
not copy large scientific inputs automatically. Frozen values are in
`parameters.json`. Start `run.cmd` on Windows or `sh run.sh` on Linux.

The destination needs no Operon installation and does not install dependencies
while running. The bundled execution kernel retains process supervision,
memory admission, per-run temporary partitions, spill support and isolated
dependency targets. External tools remain subject to the process reservation;
their internal heaps are not automatically made streamable.

`--check` validates the package and bindings. `--prepare-only` prepares the
destination offline without starting scientific computation. `--resume` uses
the existing verified resume mechanism. `--work-dir` and `--output-dir` select
working and published output locations. Do not edit immutable payload files.

Windows R needs ordinary physical paths. For a workspace with spaces, R's
temporary files use an attempt-owned directory under the OS temporary area,
recorded for recovery and removed only after the process tree has stopped. Data,
outputs and spill partitions retain their original ownership. If even the OS
temporary location is unsupported, preparation returns a path error.

## Boundaries

Export is same-platform reproducibility, not cross-compilation. GPU drivers,
OS ABI compatibility, licensed software and external services are not bundled.
Arbitrary dynamically opened files cannot be discovered from import statements;
operators must declare those resources. A system executable without a complete
portable installation is rejected rather than advertised as independent.

The automatic native canvas path currently requires one execution host. Existing
advanced RunPlan adapters and experimental multi-node/Slurm paths keep their
separate acceptance requirements. Library declarations and scientific behavior
are not rewritten by export.
