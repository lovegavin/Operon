import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.epidemic_growth_rate import EpidemicGrowthRateStep
from src.task.step.steps.epidemic_r0 import EpidemicR0Step
from src.task.step.steps.epidemic_case_fatality import EpidemicCaseFatalityStep
from src.task.step.steps.epidemic_sir_fit import EpidemicSirFitStep
from src.task.step.steps.epidemic_seir_fit import EpidemicSeirFitStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def curve():
    t = np.arange(0, 40, dtype=float)
    cases = np.round(100 * np.exp(0.12 * t)).astype(float)
    deaths = np.round(np.cumsum(cases) * 0.02)
    data = np.column_stack([t, cases, deaths])
    return Form(data=data, dims=["time", "field"],
                labels={"time": {str(int(i)): i for i in range(t.size)},
                        "field": {"time": 0, "cases": 1, "deaths": 2}},
                info={"missing_code": np.nan})


def run(step, params):
    ctx = Ctx(params)
    step().run(ctx, [curve()])
    return ctx[params["output"]]


def test_growth_rate_recovers_slope():
    out = run(EpidemicGrowthRateStep, {"output": "o", "cases_field": "cases", "window_days": 40})
    assert abs(out.data[0, 0] - 0.12) < 0.01
    assert abs(out.data[0, 1] - np.log(2) / 0.12) < 2.0


def test_r0_uses_generation_time():
    out = run(EpidemicR0Step, {"output": "o", "cases_field": "cases", "window_days": 40,
                               "generation_time_days": 5.0})
    assert abs(out.data[0, 0] - (1 + 0.12 * 5)) < 0.08


def test_cfr():
    out = run(EpidemicCaseFatalityStep, {"output": "o", "cases_field": "cases",
                                         "deaths_field": "deaths"})
    assert abs(out.data[0, 0] - out.data[0, 3] / out.data[0, 4]) < 1e-7


def test_sir_fit():
    out = run(EpidemicSirFitStep, {"output": "o", "cases_field": "cases",
                                   "population_size": 1e6})
    assert 0 < out.data[0, 0] < 2
    assert 0 < out.data[0, 1] < 1


def test_seir_fit():
    out = run(EpidemicSeirFitStep, {"output": "o", "cases_field": "cases",
                                    "population_size": 1e6, "sigma": 0.2})
    assert 0 < out.data[0, 3] < 50
