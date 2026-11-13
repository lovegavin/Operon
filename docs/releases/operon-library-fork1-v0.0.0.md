# operon-library-fork1 v0.0.0

A minimal second operator library used to exercise Operon Studio 5.1.0
multi-library coexistence.

- Package: `operon-fork1` (top-level module `operon_fork1`)
- Operator: `fork1_numeric_gini` (Gini coefficient over a numeric axis)
- Descriptor count: 1 operator, 0 Readers
- Minimum application: 5.1.0
- Format: `bundle_format=1`, `operator_protocol=3`

Import it with the label `fork1-v0.0.0` next to the main library; the two
libraries must not share operator/Reader ids, distribution names or top-level
modules.
