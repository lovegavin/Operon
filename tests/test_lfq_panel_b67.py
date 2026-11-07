import numpy as np
import pytest

from src.core import Form
from src.task.context import Context
from src.task.step.steps.lfq_median_normalize import LfqMedianNormalizeStep
from src.task.step.steps.lfq_quantile_normalize import LfqQuantileNormalizeStep
from src.task.step.steps.ms_missing_filter import MsMissingFilterStep


class Ctx(Context):
    def __init__(self, params):
        self.step_params = params
        self._values = {}

    def __setitem__(self, key, value):
        self._values[key] = value

    def __getitem__(self, key):
        return self._values[key]


def matrix():
    data = np.array(
        [[100.0, 200.0, 300.0, 400.0],
         [110.0, 210.0, 310.0, 410.0],
         [90.0, 190.0, 290.0, 390.0],
         [np.nan, 200.0, 300.0, 400.0],
         [100.0, 200.0, np.nan, 400.0]]
    )
    return Form(
        data=data,
        dims=["protein", "sample"],
        labels={
            "protein": {"p1": 0, "p2": 1, "p3": 2, "p4": 3, "p5": 4},
            "sample": {"s1": 0, "s2": 1, "s3": 2, "s4": 3},
        },
        info={"missing_code": np.nan},
    )


def run(step, params):
    form = matrix()
    ctx = Ctx(params)
    step.run(ctx, [form])
    return ctx[params["output"]]


def test_median_normalize():
    out = run(LfqMedianNormalizeStep(), {"output": "normalized"})
    med = np.array([100.0, 200.0, 300.0, 400.0])
    assert np.allclose(np.nanmedian(out.data, axis=0), np.median(med))
    assert np.isnan(out.data[3, 0]) and np.isnan(out.data[4, 2])


def test_quantile_normalize():
    out = run(LfqQuantileNormalizeStep(), {"output": "normalized"})
    a = np.sort(out.data[np.isfinite(out.data[:, 0]), 0])
    b = np.sort(out.data[np.isfinite(out.data[:, 2]), 2])
    assert np.allclose(a, b)
    assert len(a) == 4


def test_missing_filter():
    out = run(MsMissingFilterStep(), {"max_missing_fraction": 0.5, "output": "filtered"})
    assert out.data.shape == (5, 4)
    assert out.info["n_input"] == 5 and out.info["n_kept"] == 5


def test_missing_filter_drops_missing_rows():
    out = run(MsMissingFilterStep(), {"max_missing_fraction": 0.24, "output": "filtered"})
    assert out.data.shape[0] == 3
