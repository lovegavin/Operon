import numpy as np
from src.core import Form
from src.task.step.base import Step


class Ctx:
    def __init__(self, values):
        self.step_params = dict(values)
        self._v = {}

    def __setitem__(self, key, value):
        self._v[key] = value

    def __getitem__(self, key):
        return self._v[key]


def make(cols):
    names = list(cols)
    data = np.column_stack([np.asarray(cols[n], dtype=float) for n in names])
    labels = {"row": {str(i): i for i in range(data.shape[0])},
              "field": {n: i for i, n in enumerate(names)}}
    return Form(data=data, dims=["row", "field"], labels=labels, info={"missing_code": np.nan})


def run(cls, form, params=None):
    ctx = Ctx({"output": "out", "row_dim": "row", "field_dim": "field", **(params or {})})
    step = cls()
    step.name = step.definition["id"]
    step.run(ctx, [form])
    return ctx["out"]


def test_did():
    from src.task.step.steps.difference_in_differences import DifferenceInDifferencesStep
    rng = np.random.default_rng(7)
    t = np.repeat([0, 1], 100); post = np.tile(np.repeat([0, 1], 50), 2)
    y = 10 + 2 * t + 3 * post + 4 * t * post + rng.normal(0, 0.01, 200)
    out = run(DifferenceInDifferencesStep, make({"outcome": y, "treatment": t, "post": post}))
    assert abs(out.data[0, 0] - 4.0) < 0.01


def test_event_study():
    from src.task.step.steps.event_study import EventStudyStep
    units = np.repeat(np.arange(8), 10); times = np.tile(np.arange(10), 8)
    treat = ((units < 4) & (times >= 6)).astype(float)
    y = units * 0.5 + times * 0.2 + 2.0 * treat
    out = run(EventStudyStep, make({"outcome": y, "unit": units, "time": times, "treatment": treat}),
              {"min_period": -2, "max_period": 3})
    labels = out.labels["statistic"]
    assert "event_0_coef" in labels
    assert abs(out.data[0, labels["event_0_coef"]] - 2.0) < 0.1


def test_synthetic_control():
    from src.task.step.steps.synthetic_control import SyntheticControlStep
    rng = np.random.default_rng(3)
    n_time, n_donor = 12, 5
    base = np.linspace(1, 3, n_time)
    donors = np.column_stack([base + d * 0.2 + rng.normal(0, 0.005, n_time) for d in range(n_donor)])
    treated = donors[:, 0].copy()
    treated[6:] += 1.5
    unit = np.concatenate([np.zeros(n_time), np.repeat(np.arange(1, n_donor + 1), n_time)])
    time = np.concatenate([np.arange(n_time), np.tile(np.arange(n_time), n_donor)])
    y = np.concatenate([treated, donors.T.ravel()])
    out = run(SyntheticControlStep, make({"outcome": y, "unit": unit, "time": time,
                                          "treatment": (unit == 0).astype(float)}), {"pre_end": 5})
    assert abs(out.data[0, 0] - 1.5) < 0.2


def test_aipw():
    from src.task.step.steps.doubly_robust_ate import DoublyRobustAteStep
    rng = np.random.default_rng(11)
    n = 4000
    x = rng.normal(size=n)
    ps = 1 / (1 + np.exp(-1.2 * x))
    t = rng.binomial(1, ps)
    y = 2.0 * t + x + rng.normal(0, 0.5, n)
    out = run(DoublyRobustAteStep, make({"outcome": y, "treatment": t, "x1": x}))
    assert abs(out.data[0, 0] - 2.0) < 0.15


def test_mediation():
    from src.task.step.steps.mediation_analysis import MediationAnalysisStep
    rng = np.random.default_rng(5)
    n = 2000
    t = rng.normal(size=n)
    m = 0.8 * t + rng.normal(0, 0.5, n)
    y = 1.0 * t + 2.0 * m + rng.normal(0, 0.5, n)
    out = run(MediationAnalysisStep, make({"outcome": y, "treatment": t, "mediator": m}))
    labels = out.labels["statistic"]
    acme = out.data[0, labels["acme"]]
    assert abs(acme - 1.6) < 0.15
