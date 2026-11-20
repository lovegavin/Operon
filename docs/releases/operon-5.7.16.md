# Operon Studio 5.7.16

## Fixed

- **F-112** — files written by an isolated step are copied out of the throw-away
  bridge directory before it is removed. Operators that publish a file result
  (`vcf_*`, `liftover_*`, `coding_variant_filter`, `variant_consequence`,
  `alphafold2_rank_models`) used to fail the next validation with
  `missing file for role ...: /tmp/envbridge-*/...`; they now keep the file under
  the job's `.operon-artifacts` directory and pass validation.
- **F-113** — the dependency preflight looks for external tools inside the
  environment an operator declares, and reports a missing environment before it
  reports missing tools. `antismash`, `amrfinder`, `quast` and friends used to be
  rejected as `not on PATH` even though the binary sat in the installed
  environment; a declared but uninstalled environment now says so.
- **F-114** — `core` declares `biopython`, and `hic` declares `psutil`, matching
  what their operators import.

## Verification

Clean install of the shipped payload reports 5.7.16, library main-v1.1.10 with
1,074 operators, eighteen environments, and the installer actions answered by the
service: prepare, cancel, retry, dependency download (409 while not ready),
resource download and log. See the 5.7.16 test report for the recorded numbers.

## Library

`library` 1.1.10 ships the same operator set with the requirements above; no
operator contract or default value changed.

## Readiness and installer semantics

- `operon record` and the runtime panel now use exactly five environment
  states: *not ready*, *ready*, *queued*, *installing*, *installation
  failed*.  The previous *not created* / *needs update* / *preparation
  failed* wording is gone.
- **Ready means dependencies and resources are both complete.**  An
  environment whose interpreter exists but whose declared packages or
  resources are missing is reported as *not ready* (backend status
  `incomplete`), and the panel lists the missing items.
- Installing is a single action.  Pressing *Install dependencies* on an
  environment that is not ready first creates the environment and installs
  everything it declares, then continues with the requested dependency — the
  request returns a job instead of a 4xx.
- Every control reports its outcome: install, reinstall, cancel, retry,
  dependency install, resource download and log all surface a message, so
  nothing fails silently.
