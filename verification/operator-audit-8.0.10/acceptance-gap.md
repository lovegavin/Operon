# 8.0.8 L5 acceptance gap

Recorded on 2026-11-13 after revising the five-layer test standard.

## What was actually run

- The final Linux and Windows bundles were built and SHA256-recorded.
- `verify_library_release.py` ran on Studio 4.0.8 with `OPERON_FORWARD_MINIMUM=1`; it reported `passed: true`.
- `environment_install.prepare("openmm81")` ran on Studio 4.1.9 from a source-tree copy of the manifest, reached `ready`, and the bundled PDBFixer processed 1MEL.

## What was not run before publish

The final `.operon-library.zip` was not installed into a clean 4.1.9 profile and the acceptance route was not executed from that installed library. The environment probe used the source manifest, not the manifest inside the published artifact. Under the revised L5 standard this is `verification incomplete`, even though the source-level probe passed.

## Status

8.0.8 remains published because tags and release assets are immutable. It is not evidence for the revised gate. 8.0.9 and later must produce `verification/release-acceptance-<version>.json` from the frozen artifact and pass `scripts/check_release_acceptance.py` before publishing.

No library code defect was found in this gap; the defect was the acceptance procedure that allowed a source probe to be reported as installation evidence.
