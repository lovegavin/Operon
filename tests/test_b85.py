import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.reader.readers._table_common import table_form
from src.task.step.steps.mlp_classifier import MlpClassifierStep
from src.task.step.steps.mlp_regressor import MlpRegressorStep
from src.task.step.steps.autoencoder_anomaly import AutoencoderAnomalyStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def make_form(df, labels):
    return table_form(
        df,
        ["row", "field"],
        labels={"field": "builtin"},
        format_name="table",
        encoders_cfg={},
        row_labels=[f"r{i}" for i in range(len(df))],
    )


def run_step(cls, df, op_id, **params):
    step = cls()
    form = make_form(df, {})
    ctx = Ctx({"output": op_id, **params})
    step.run(ctx, [form])
    return ctx[op_id]


def test_mlp_classifier_separable():
    df = pd.DataFrame({
        "x1": [0.0, 1.0, 0.0, 1.0, 2.0, 2.0],
        "x2": [0.0, 0.0, 1.0, 1.0, 0.0, 1.0],
        "label": [0, 0, 0, 1, 1, 1],
    })
    out = run_step(MlpClassifierStep, df, "mlp", epochs=300, seed=3)
    acc = float(out.data[0, 0])
    assert acc >= 0.99
    assert out.dims == ["entry", "statistic"]


def test_mlp_regressor_linear():
    x = np.arange(6, dtype=float)
    df = pd.DataFrame({"x": x, "target": 2.0 * x})
    out = run_step(MlpRegressorStep, df, "reg", epochs=400, seed=3)
    r2 = float(out.data[0, 2])
    rmse = float(out.data[0, 0])
    assert r2 > 0.95
    assert rmse < 0.6


def test_autoencoder_rank_one():
    t = np.arange(6, dtype=float)
    df = pd.DataFrame({"a": t, "b": 2.0 * t})
    out = run_step(AutoencoderAnomalyStep, df, "ae", epochs=300, seed=3)
    assert float(out.data[0, 0]) < 20.0
    assert float(out.data[0, 3]) == 0.0
