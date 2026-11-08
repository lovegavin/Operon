import numpy as np
import pytest

from src.core import Form
from src.core.errors import StepError
from src.task.step.steps.iv_2sls import Iv2slsStep
from src.task.step.steps.regression_discontinuity import RegressionDiscontinuityStep
from src.task.step.steps.propensity_score_matching import PropensityScoreMatchingStep


class Ctx(dict):
    def __init__(self, **params):
        super().__init__()
        self.step_params = params


def frame(columns, names):
    data = np.column_stack(columns).astype(float)
    return Form(data=data, dims=["row", "field"],
                labels={"row": {str(i): i for i in range(data.shape[0])},
                        "field": {n: i for i, n in enumerate(names)}})


def test_iv_recovers_structural_coefficient():
    rng = np.random.default_rng(3)
    n = 400
    z = rng.normal(size=n)
    v = rng.normal(size=n)
    x = 0.9 * z + v
    y = 2.0 * x + rng.normal(scale=0.5, size=n)
    form = frame([y, x, z], ["y", "x", "z"])
    ctx = Ctx(output="o", sample_dim="row", feature_dim="field", outcome_label="y",
              endog_labels=["x"], instrument_labels=["z"], exog_labels=[])
    Iv2slsStep().run(ctx, [form])
    out = ctx["o"]
    coef = out.data[out.labels["term"]["x"], out.labels["statistic"]["coef"]]
    assert abs(coef - 2.0) < 0.15
    assert out.labels["statistic"]["ci_low"] == 4


def test_rdd_recovers_jump():
    rng = np.random.default_rng(5)
    r = np.linspace(-2, 2, 300)
    y = 1.0 * r + 3.0 * (r >= 0) + rng.normal(scale=0.05, size=r.size)
    form = frame([y, r], ["y", "run"])
    ctx = Ctx(output="o", y_column="y", running_column="run", cutoff=0.0, bandwidth=0.0)
    RegressionDiscontinuityStep().run(ctx, [form])
    out = ctx["o"]
    jump = out.data[0, out.labels["statistic"]["jump"]]
    assert abs(jump - 3.0) < 0.1
    assert out.data[0, out.labels["statistic"]["n_left"]] == 150


def test_psm_recovers_att():
    rng = np.random.default_rng(11)
    n = 300
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    ps = 1 / (1 + np.exp(-(0.8 * x1 - 0.4 * x2)))
    t = (rng.random(n) < ps).astype(float)
    y = 2.0 * t + 0.5 * x1 + rng.normal(scale=0.3, size=n)
    form = frame([t, y, x1, x2], ["t", "y", "x1", "x2"])
    ctx = Ctx(output="o", treatment_column="t", outcome_column="y",
              covariate_columns="x1,x2", caliper=0.05)
    PropensityScoreMatchingStep().run(ctx, [form])
    out = ctx["o"]
    att = out.data[0, out.labels["statistic"]["att"]]
    assert abs(att - 2.0) < 0.35
    assert out.data[0, out.labels["statistic"]["n_matched"]] > 20
