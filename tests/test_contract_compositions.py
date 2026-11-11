"""Static composition matrix and dependency audit for declared operator outputs.

The five-layer standard historically tested one positive contract and one
deliberate violation per operator.  That could not catch a producer whose
output was joinable but not groupable (BE-06).  These tests treat every
declared output dimension and every declared label as a composition edge:

* every declared dimension must satisfy ``join``'s input contract;
* every declared label must satisfy ``aggregate``'s ``group_col`` contract;
* every label must actually survive an ``aggregate`` run;
* every numeric 2D output using a statistic-like second axis must label it;
* every import probe needs a declared pip dependency or a named environment.
"""

from __future__ import annotations

import numpy as np
from src.core import Form
from src.core.contracts import compatible
from src.task import STEPS
from src.task.step.steps.aggregate import AggregateStep

STATISTIC_AXES = {"statistic", "score"}

# The statistic column label is a runtime parameter for these PRS operators.
# The output schema therefore cannot name it statically; the reason is part
# of the audited allowlist instead of being silently ignored.
DYNAMIC_STATISTIC_LABELS = {
    "prs_af_filter": ("statistic", "statistic label is weight_label (runtime parameter)"),
    "prs_harmonize": ("statistic", "statistic label is weight_label (runtime parameter)"),
    "prs_ld_clump": ("statistic", "statistic label is weight_label (runtime parameter)"),
}


def _dim_name(dim):
    if isinstance(dim, str):
        return dim
    if isinstance(dim, dict) and isinstance(dim.get("default"), str):
        return dim["default"]
    return None


def _output_schemas():
    for name, step in STEPS.items():
        output = (step.definition.get("contracts") or {}).get("output") or {}
        schema = output.get("schema") or {}
        if not schema.get("numeric") or schema.get("ndim") != 2:
            continue
        raw_dims = schema.get("dims")
        if not isinstance(raw_dims, list) or len(raw_dims) != 2:
            continue
        dims = [_dim_name(dim) for dim in raw_dims]
        if not all(dims):
            continue
        yield name, {**schema, "dims": dims}


def test_every_declared_dimension_supports_join():
    failures = []
    for name, schema in _output_schemas():
        for dim in schema["dims"]:
            result = compatible(
                schema,
                {"ndim": 2, "numeric": True, "dims": [dim]},
            )
            if result["status"] != "compatible":
                failures.append((name, dim, result))
    assert not failures, failures


def test_every_declared_label_supports_aggregate_contract():
    failures = []
    for name, schema in _output_schemas():
        labels = schema.get("labels") or {}
        for dim, values in labels.items():
            if dim != schema["dims"][1] or not values:
                continue
            for label in values:
                result = compatible(
                    schema,
                    {
                        "ndim": 2,
                        "numeric": True,
                        "dims": [schema["dims"][0]],
                        "labels_axis": [{"axis": 1, "values": [label]}],
                    },
                )
                if result["status"] != "compatible":
                    failures.append((name, dim, label, result))
    assert not failures, failures


def test_statistic_axes_are_always_labelled():
    failures = []
    for name, schema in _output_schemas():
        if schema["dims"][1] not in STATISTIC_AXES:
            continue
        labels = (schema.get("labels") or {}).get(schema["dims"][1]) or []
        if not labels and name not in DYNAMIC_STATISTIC_LABELS:
            failures.append(name)
    assert not failures, failures


class _Context:
    def __init__(self, params):
        self.step_params = params
        self.values = {}
        self.metadata = {}

    def __setitem__(self, key, value):
        self.values[key] = value


def _run_aggregate(row_dim, group_dim, label):
    row_labels = {f"row{i}": i for i in range(3)}
    group_labels = {f"g{i}": i for i in range(2)}
    # One numeric group per row, encoded as 0/1; no encoder is needed.
    groups = Form(
        np.asarray([[0.0], [1.0], [0.0]], dtype=float),
        dims=[row_dim, group_dim],
        labels={row_dim: row_labels, group_dim: {label: 0}},
    )
    values = Form(
        np.asarray([[1.0], [2.0], [3.0]], dtype=float),
        dims=[row_dim, "value"],
        labels={row_dim: row_labels, "value": {"value": 0}},
    )
    ctx = _Context(
        {"dim": row_dim, "group_col": label, "method": "mean", "output": "out"}
    )
    AggregateStep().run(ctx, [values, groups])
    return ctx.values["out"]


def test_every_declared_label_actually_aggregates():
    for name, schema in _output_schemas():
        labels = schema.get("labels") or {}
        for dim, values in labels.items():
            if dim != schema["dims"][1] or not values:
                continue
            for label in values:
                result = _run_aggregate(schema["dims"][0], dim, label)
                assert result.data.ndim == 2, (name, dim, label)
                assert result.data.shape[0] > 0, (name, dim, label)


def test_dynamic_label_allowlist_is_current():
    for name, (dimension, reason) in DYNAMIC_STATISTIC_LABELS.items():
        output = (STEPS[name].definition.get("contracts") or {}).get("output") or {}
        schema = output.get("schema") or {}
        dims = [_dim_name(item) for item in schema.get("dims") or []]
        assert len(dims) == 2 and dims[1] == dimension, (name, dims)
        assert reason
        assert not (schema.get("labels") or {}).get(dimension), name


def test_import_probes_have_an_explicit_dependency_source():
    failures = []
    for name, step in STEPS.items():
        definition = step.definition
        imports = definition.get("dependency_imports") or []
        if not imports:
            continue
        dependencies = definition.get("dependencies") or []
        environment = (definition.get("resources") or {}).get("environment")
        if not dependencies and not environment:
            failures.append((name, imports))
    assert not failures, failures
