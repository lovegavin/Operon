# Operator audit scripts

These scripts produce the evidence in `verification/operator-audit-7.0.2/`
for library 7.0.2 against Studio 3.1.6.

| script | layer | purpose |
| --- | --- | --- |
| `l0_static.py` | L0 | AST/descriptor/contract/documentation consistency for every operator and Reader |
| `l1_contract.py` | L1 | synthesize a valid Form per port, resolve bindings, execute `run`, and mutate each `info` predicate for negative checks |
| `gen_cov.py` | L3 | generate CSV-backed single-input 2D route templates for uncovered operators |
| `gen_cov2.py` | L3 | generate arity 0/1/2 route templates for uncovered operators |
| `check_any.py` | L3 | run `scripts/run.py --check` or full execution over a generated route set |
| `run_routes.py` | L3 | replay the 78 builtin route templates and classify missing input data |

Run from the repository root with the library interpreter, for example:

```
python scripts/operator_audit/l0_static.py
python scripts/operator_audit/l1_contract.py
```

Generated route sets are written under `/tmp` and are not part of the seeded
catalog. Evidence lives in `verification/operator-audit-7.0.2/`.
