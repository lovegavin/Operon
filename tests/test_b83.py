import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.core.errors import StepError  # noqa: F401
from src.reader.readers._table_common import table_form
from src.task.step.steps.crispr_mit_specificity import CrisprMitSpecificityStep
from src.task.step.steps.fba_flux_balance import FbaFluxBalanceStep
from src.task.step.steps.uplift_qini_curve import UpliftQiniCurveStep
from src.task.step.steps.uplift_t_learner import UpliftTLearnerStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def test_uplift_t_learner_constant_arms():
    df = pd.DataFrame({
        "id": ["a", "b", "c", "d"],
        "treatment": [0.0, 0.0, 1.0, 1.0],
        "outcome": [1.0, 1.0, 3.0, 3.0],
        "x1": [0.0, 1.0, 0.0, 1.0],
    })
    form = table_form(df, ["row", "field"], labels={"field": "builtin"}, format_name="table", encoders_cfg={}, row_labels=["a", "b", "c", "d"])
    ctx = Ctx({"row_dim": "row", "field_dim": "field", "output": "output"})
    UpliftTLearnerStep().run(ctx, [form])
    out = ctx["output"]
    assert out.data.shape == (4, 3)
    assert np.allclose(out.data[:, 2], 2.0)
    assert out.labels["statistic"]["uplift"] == 2


def test_uplift_qini_curve_monotone_fraction():
    df = pd.DataFrame({
        "id": ["a", "b", "c", "d"],
        "treatment": [0.0, 1.0, 0.0, 1.0],
        "outcome": [1.0, 4.0, 2.0, 5.0],
        "x1": [0.0, 1.0, 0.0, 1.0],
    })
    form = table_form(df, ["row", "field"], labels={"field": "builtin"}, format_name="table", encoders_cfg={}, row_labels=["a", "b", "c", "d"])
    ctx = Ctx({"row_dim": "row", "field_dim": "field", "n_bins": 2, "output": "output"})
    UpliftQiniCurveStep().run(ctx, [form])
    out = ctx["output"]
    assert out.data.shape[0] >= 2
    frac = out.data[:, 0]
    assert np.all(np.diff(frac) > 0)


def test_fba_flux_balance_chain():
    stoich = Form(np.array([[-1.0, 1.0], [1.0, -1.0]]), dims=["metabolite", "reaction"], labels={"metabolite": {"a": 0, "b": 1}, "reaction": {"r1": 0, "r2": 1}})
    bounds = Form(np.array([[0.0, 10.0, 1.0], [0.0, 10.0, 1.0]]), dims=["reaction", "field"], labels={"reaction": {"r1": 0, "r2": 1}, "field": {"lower": 0, "upper": 1, "objective": 2}})
    ctx = Ctx({"row_dim": "reaction", "field_dim": "field", "output": "output"})
    FbaFluxBalanceStep().run(ctx, [stoich, bounds])
    out = ctx["output"]
    assert np.isclose(out.data[0, 0], 10.0)
    assert np.isclose(out.data[1, 0], 10.0)
    assert np.isclose(out.data[-1, 0], 20.0)


def test_crispr_mit_single_mismatch():
    guide = "ACGTACGTACGTACGTACGT"
    off = "ACGTACGTACGTACGTACGA"
    df = pd.DataFrame({"id": ["g1"], "guide": [guide], "off_target": [off]})
    form = table_form(df, ["row", "field"], labels={"field": "builtin"}, format_name="table", encoders_cfg={}, row_labels=["g1"])
    ctx = Ctx({"row_dim": "row", "field_dim": "field", "output": "output"})
    CrisprMitSpecificityStep().run(ctx, [form])
    out = ctx["output"]
    assert np.isclose(out.data[0, 0], 41.7)
    assert out.data[0, 1] == 1
    assert out.data[0, 2] == 19
