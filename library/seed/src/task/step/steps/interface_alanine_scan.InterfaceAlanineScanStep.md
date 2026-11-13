<!-- operon:generated -->
# Interface alanine scan

## Purpose

> Computational alanine scanning on a protein interface with MM/GBSA.

## Inputs and outputs

Kind: `operator`. Operator ID: `interface_alanine_scan`.
Input count: `1`.
Read the structured `contracts` section before connecting nodes. It includes
the accepted data types, dimension constraints and output propagation rule.

## Parameter guidance

The adjacent parameter JSON owns defaults, valid choices, ranges and required
fields. Request the generated `parameters` section and `parameters_schema` for
the exact interface; do not infer parameter names from prose.
Saved routes keep their own parameter values independently of current defaults.

## Interpretation

Check output metadata and labels before downstream analysis. The declared output
contract describes the representation; it does not establish biological validity
or statistical assumptions for a particular dataset.

## Runtime environment

Declared Python requirements: `openmm==8.1.1`, `numpy==1.26.4`. Prepare them explicitly in the selected execution environment; registration and application startup do not install them.

This operator executes in the dedicated `openmm81` interpreter; see docs/large_resources.md for resolution and overrides.

## Limitations

Declared memory modes: full. Operon retains the existing planner, disk-backed
inputs and emergency spill behavior; full-mode operators still require their
declared working set. This generated reference has not been independently
scientifically reviewed.

## Scientific limitations

This operator is a single-point MM/GBSA estimate. It does not include entropy,
ensemble averaging or calibration, so `delta_delta_kj` must not be reported as a
binding affinity or used alone to rank hotspots. Prefer replicated runs or an
ensemble, and treat one structure and one protocol as a screen rather than a
measurement.

Glycine-to-alanine substitutions are flagged with `flag="gly_to_ala"` and
`excluded_from_ranking=true`: glycine has no side chain, so the mutation adds a
methyl group and is not a comparable alanine substitution at a packed
interface. Those rows remain in the output for inspection but should be kept out
of rankings and CDR/interface shares.

When the same residue numbering appears in several chains, `copy_replicates`
reports pairwise Spearman correlation and sign-conflict fraction. Low agreement
means the copy-level ranking is not reproducible; do not report hotspots from
that run.

## Examples

Use the registry to discover compatible Readers and validate a complete workflow
before execution. This generated page does not claim an executable scientific
example. Add a tested example and replace this generated page with authored
guidance when extending this operator.

## Source

Implementation: `src/task/step/steps/interface_alanine_scan.py` (`InterfaceAlanineScanStep`).
