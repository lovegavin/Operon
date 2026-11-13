# Operon Library v0.1.0

Additive release on the independent library line. The bundle format, operator
protocol and compatibility range are unchanged from v0.0.0.

## Compatibility

- Application: Operon Studio **5.0.0** or newer (same build as v0.0.0 served).
- Bundle format: **1**; operator protocol: version **3**, revision **3.7**.

## New operators

| Operator | Output |
|---|---|
| `sequence_dinucleotide_frequency` | 16 dinucleotide rows with `count`, `frequency`, `cpg_observed_expected` |
| `numeric_gini_coefficient` | `gini`, `n`, `total`, `mean` |
| `diversity_simpson` | `simpson`, `inverse_simpson`, `evenness`, `richness` |

Each operator has a literal protocol declaration, explicit `data_formats` for
every port, an independent parameter schema, English reference documentation and
hand-computed unit oracles (`tests/test_b81_operators.py`).

## Contents

- 1,066 operators, 108 Readers, 7 packages, 79 built-in route templates.
- Rebuilt route collection `operon-routes-v0.1.0.zip`: every route pin is
  `{package, version, code_sha}` from this library build. Route collections from
  v0.0.0 are intentionally rejected because `operon-core` changed identity.

## Evidence

- `tests/test_b81_operators.py`: 8 passed (dinucleotide counts and CpG o/e,
  Gini pairwise/rank oracles, Simpson degenerate cases, arity and dimension
  validation).
- `operon registry check`: 1,066 operators, 108 readers, errors `[]`.
- `operon_library_builder gate`: all 7 packages verified against their wheels,
  identities and archives.
