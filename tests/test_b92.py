from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.steps.causal_forest_ate import CausalForestAteStep
from src.task.step.steps.causal_forest_cate import CausalForestCateStep
from src.task.step.steps.causal_forest_importance import CausalForestImportanceStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def frame():
    rng = np.random.default_rng(3)
    n = 60
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    t = (x1 + rng.normal(size=n) > 0).astype(float)
    y = 2.0 * t + x1 - 0.5 * x2 + rng.normal(scale=0.2, size=n)
    data = np.column_stack([x1, x2, t, y])
    return Form(data=data, dims=["row", "field"], labels={"field": {"x1": 0, "x2": 1, "t": 2, "y": 3}})


def base(**kw):
    p = {"output": "out", "row_dim": "row", "field_dim": "field", "y_column": "y", "t_column": "t",
         "n_estimators": 100, "min_samples_leaf": 5, "max_depth": 2, "seed": 7}
    p.update(kw)
    return p


def test_ate_close_to_truth():
    ctx = Ctx(base())
    CausalForestAteStep().run(ctx, [frame()])
    out = ctx["out"]
    assert out.data.shape == (1, 6)
    ate = float(out.data[0, 0])
    assert abs(ate - 2.0) < 0.8, ate
    assert float(out.data[0, 2]) < ate < float(out.data[0, 3])


def test_cate_mean_matches_ate():
    ctx = Ctx(base())
    CausalForestCateStep().run(ctx, [frame()])
    out = ctx["out"]
    assert out.data.shape == (60, 3)
    assert abs(float(out.data[:, 0].mean()) - 2.0) < 0.8
    assert np.all(out.data[:, 1] <= out.data[:, 0] + 1e-9)
    assert np.all(out.data[:, 0] <= out.data[:, 2] + 1e-9)


def test_importance_sums_to_one():
    ctx = Ctx(base())
    CausalForestImportanceStep().run(ctx, [frame()])
    out = ctx["out"]
    assert out.data.shape == (2, 2)
    assert abs(float(out.data[:, 1].sum()) - 1.0) < 1e-6
    assert np.all(out.data[:, 0] >= 0)
