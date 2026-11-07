import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.ms1_feature_detect import Ms1FeatureDetectStep
from src.task.step.steps.ms1_isotope_pattern import Ms1IsotopePatternStep
from src.task.step.steps.metabolite_mass_match import MetaboliteMassMatchStep


class Ctx:
    def __init__(self, params):
        self.step_params = params
        self._v = {}

    def __setitem__(self, k, v):
        self._v[k] = v

    def __getitem__(self, k):
        return self._v[k]

    def get(self, k, default=None):
        return self._v.get(k, default)


def form(data, dims, labels):
    f = Form(data=np.asarray(data, dtype=float), dims=dims, labels=labels,
             info={"missing_code": np.nan})
    f.validate()
    return f


def test_feature_detect():
    data = [[1.0, 100.0, 500.0], [1.0, 100.1, 5000.0], [1.0, 100.2, 400.0],
            [1.0, 101.0, 100.0], [2.0, 200.0, 300.0], [2.0, 200.1, 1200.0],
            [2.0, 200.2, 600.0]]
    f = form(data, ["peak", "field"],
             {"peak": {f"p{i}": i for i in range(len(data))},
              "field": {"scan": 0, "mz": 1, "intensity": 2}})
    ctx = Ctx({"peak_dim": "peak", "field_dim": "field", "output": "features",
               "min_intensity": 100.0, "min_prominence": 100.0})
    Ms1FeatureDetectStep().run(ctx, [f])
    out = ctx["features"]
    assert out.data.shape[0] == 2
    assert list(out.labels["statistic"]) == ["mz", "intensity", "peak_index", "scan"]


def test_isotope_pattern():
    data = [[181.0712, 1000.0], [182.0745, 60.0], [183.0778, 10.0]]
    f = form(data, ["peak", "field"], {"peak": {"p0": 0, "p1": 1, "p2": 2},
                                       "field": {"mz": 0, "intensity": 1}})
    ctx = Ctx({"peak_dim": "peak", "field_dim": "field", "output": "iso",
               "formula": "C6H12O6", "charge": 1, "tolerance_ppm": 50.0})
    Ms1IsotopePatternStep().run(ctx, [f])
    out = ctx["iso"]
    assert out.data.shape[0] >= 3
    assert abs(out.data[0, 3]) < 50.0


def test_mass_match():
    feats = [[181.0712, 1000.0], [100.0, 50.0]]
    ff = form(feats, ["feature", "field"],
              {"feature": {"f0": 0, "f1": 1}, "field": {"mz": 0, "intensity": 1}})
    db = [[180.0634], [342.1162]]
    df = form(db, ["entry", "database_field"],
              {"entry": {"glucose": 0, "sucrose": 1}, "database_field": {"neutral_mass": 0}})
    ctx = Ctx({"feature_dim": "feature", "field_dim": "field", "entry_dim": "entry",
               "database_field_dim": "database_field", "output": "matches",
               "tolerance_ppm": 20.0})
    MetaboliteMassMatchStep().run(ctx, [ff, df])
    out = ctx["matches"]
    assert out.data.shape[0] == 1
    assert abs(float(out.data[0, 2])) < 20.0
