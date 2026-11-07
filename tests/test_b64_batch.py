import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.sc_batch_ilisi import ScBatchIlisiStep
from src.task.step.steps.sc_batch_kbet import ScBatchKbetStep


class Ctx:
    def __init__(self, params):
        self.step_params = params
        self._values = {}

    def __setitem__(self, key, value):
        self._values[key] = value

    def __getitem__(self, key):
        return self._values[key]


def graph_form(w):
    n = w.shape[0]
    return Form(data=w, dims=["cell", "cell2"],
                labels={"cell": {f"c{i}": i for i in range(n)},
                        "cell2": {f"c{i}": i for i in range(n)}},
                info={"missing_code": np.nan})


def batch_form(batch):
    n = len(batch)
    x = np.asarray(batch, dtype=float).reshape(-1, 1)
    return Form(data=x, dims=["cell", "batch"],
                labels={"cell": {f"c{i}": i for i in range(n)}, "batch": {"batch": 0}},
                info={"missing_code": np.nan})


def test_kbet_perfectly_separated():
    w = np.zeros((6, 6))
    for i in range(3):
        for j in range(3):
            if i != j:
                w[i, j] = 1.0
                w[i + 3, j + 3] = 1.0
    step = ScBatchKbetStep()
    ctx = Ctx({"output": "out", "alpha": 0.5})
    step.run(ctx, [graph_form(w), batch_form([0, 0, 0, 1, 1, 1])])
    out = ctx["out"]
    assert out.data.shape == (6, 4)
    assert np.all(out.data[:, 2] == 1.0)
    assert out.data[0, 0] == pytest.approx(2.0)


def test_ilisi_extremes():
    w = np.zeros((6, 6))
    for i in range(3):
        for j in range(3):
            if i != j:
                w[i, j] = 1.0
                w[i + 3, j + 3] = 1.0
    step = ScBatchIlisiStep()
    ctx = Ctx({"output": "out"})
    step.run(ctx, [graph_form(w), batch_form([0, 0, 0, 1, 1, 1])])
    out = ctx["out"]
    assert np.allclose(out.data[:, 0], 1.0)
    assert np.allclose(out.data[:, 1], 0.0)

    w2 = np.ones((6, 6))
    np.fill_diagonal(w2, 0.0)
    ctx = Ctx({"output": "out"})
    step.run(ctx, [graph_form(w2), batch_form([0, 0, 0, 1, 1, 1])])
    out = ctx["out"]
    assert np.allclose(out.data[:, 0], 25/13)
    assert np.allclose(out.data[:, 1], 12/13)
