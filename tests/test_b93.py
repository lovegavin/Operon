import numpy as np

from src.core import Form
from src.task.step.steps.sarimax_forecast import SarimaxForecastStep
from src.task.step.steps.isolation_forest_anomaly import IsolationForestAnomalyStep
from src.task.step.steps.lof_outlier_score import LofOutlierScoreStep


class Ctx(dict):
    @property
    def step_params(self):
        return self


def labelled(rows, columns):
    data = np.asarray(rows, dtype=float)
    return Form(data=data, dims=["row", "field"],
                labels={"row": {str(i): i for i in range(len(rows))},
                        "field": {c: i for i, c in enumerate(columns)}})


def test_sarimax_ar1_forecast():
    rng = np.random.default_rng(3)
    n = 40
    y = np.zeros(n)
    for i in range(1, n):
        y[i] = 0.5 * y[i - 1] + rng.normal(0.0, 0.3)
    form = labelled(np.column_stack([np.arange(n, dtype=float), y]), ["time", "value"])
    ctx = Ctx(output="fc", row_dim="row", field_dim="field", time_column="time",
              value_column="value", order_p=1, order_d=0, order_q=0, steps=2)
    SarimaxForecastStep().run(ctx, [form])
    out = ctx["fc"]
    assert out.data.shape == (2, 3)
    assert (out.data[:, 1] <= out.data[:, 0]).all() and (out.data[:, 0] <= out.data[:, 2]).all()
    y0 = y[1:]
    y1 = y[:-1]
    A = np.column_stack([np.ones_like(y1), y1])
    coef, *_ = np.linalg.lstsq(A, y0, rcond=None)
    manual = coef[0] + coef[1] * y[-1]
    assert abs(out.data[0, 0] - manual) < 0.2


def test_isolation_forest_flags_far_point():
    rows = [[0.0, 0.0], [0.1, 0.0], [0.0, 0.1], [0.1, 0.1], [0.05, 0.05], [0.2, 0.0], [10.0, 10.0]]
    form = labelled(rows, ["x", "y"])
    ctx = Ctx(output="iforest", row_dim="row", field_dim="field", n_estimators=80,
              sample_size=7, seed=11, threshold=0.6)
    IsolationForestAnomalyStep().run(ctx, [form])
    out = ctx["iforest"]
    assert out.data.shape == (7, 3)
    assert out.data[-1, 2] == 1.0
    assert out.data[-1, 0] == out.data[:, 0].max()
    assert out.data[:-1, 2].sum() <= 2


def test_lof_flags_far_point():
    rows = [[0.0, 0.0], [0.1, 0.0], [0.0, 0.1], [0.1, 0.1], [0.05, 0.05], [10.0, 10.0]]
    form = labelled(rows, ["x", "y"])
    ctx = Ctx(output="lof", row_dim="row", field_dim="field", k=3, threshold=1.5)
    LofOutlierScoreStep().run(ctx, [form])
    out = ctx["lof"]
    assert out.data.shape == (6, 3)
    assert out.data[-1, 0] > 2.0
    assert out.data[-1, 2] == 1.0
    assert out.data[:-1, 0].max() < 1.5
