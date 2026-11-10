"""Tests for aggregate when the group table shares the data field dimension."""

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.aggregate import AggregateStep


class Ctx(dict):
    def __init__(self, inputs, params):
        super().__init__()
        self.inputs = inputs
        self.step_params = params
        self.artifacts = {}
        self.metadata = {}

    def artifact_path(self, name):
        return f"/tmp/{name}"


def _form(data, dims, labels):
    return Form(data=np.asarray(data, dtype=np.float32), dims=dims, labels=labels)


def test_aggregate_promotes_shared_group_dimension():
    data = _form(
        [[1.0, 0.0], [2.0, 0.0], [3.0, 1.0], [4.0, 1.0]],
        ["residue", "field"],
        {"residue": {"r0": 0, "r1": 1, "r2": 2, "r3": 3},
         "field": {"bsa": 0, "cdr_index": 1}},
    )
    groups = _form(
        [[0.0], [0.0], [1.0], [1.0]],
        ["residue", "field"],
        {"residue": {"r0": 0, "r1": 1, "r2": 2, "r3": 3},
         "field": {"cdr_index": 0}},
    )
    ctx = Ctx([data, groups], {"dim": "residue", "group_col": "cdr_index", "method": "sum", "output": "out"})
    AggregateStep().run(ctx, [data, groups])
    out = ctx["out"]
    assert out.dims == ["cdr_index", "field"]
    assert out.data.shape == (2, 1)
    assert np.allclose(out.data[:, 0], [3.0, 7.0])
    assert out.labels["field"] == {"bsa": 0}
    assert list(out.labels["cdr_index"]) == ["0", "1"]


def test_aggregate_keeps_group_dim_when_distinct():
    data = _form(
        [[1.0], [2.0], [3.0], [4.0]],
        ["residue", "score"],
        {"residue": {"r0": 0, "r1": 1, "r2": 2, "r3": 3}, "score": {"s": 0}},
    )
    groups = _form(
        [[0.0], [0.0], [1.0], [1.0]],
        ["residue", "group"],
        {"residue": {"r0": 0, "r1": 1, "r2": 2, "r3": 3}, "group": {"cdr": 0}},
    )
    ctx = Ctx([data, groups], {"dim": "residue", "group_col": "cdr", "method": "mean", "output": "out"})
    AggregateStep().run(ctx, [data, groups])
    out = ctx["out"]
    assert out.dims == ["group", "score"]
    assert np.allclose(out.data[:, 0], [1.5, 3.5])
