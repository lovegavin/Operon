import numpy as np
from src.core import Form
from src.core.encoding import LabelEncoder
from src.task.step.base import Step


class Ctx:
    def __init__(self, values):
        self.step_params = dict(values)
        self._v = {}

    def __setitem__(self, key, value):
        self._v[key] = value

    def __getitem__(self, key):
        return self._v[key]


def _form():
    enc = LabelEncoder()
    enc.fit_transform(np.array(["chr22"] * 4, dtype=object))
    data = np.array([[22, 100000, 10, 0, 0, 10],
                     [22, 100100, 8, 2, 2, 8],
                     [22, 100200, 6, 4, 4, 6],
                     [22, 100300, 4, 6, 6, 4]], dtype=float)
    labels = {"probe": {"p0": 0, "p1": 1, "p2": 2, "p3": 3},
              "field": {"chrom": 0, "pos": 1, "group1_methylated": 2, "group1_unmethylated": 3,
                        "group2_methylated": 4, "group2_unmethylated": 5}}
    return Form(data=data, dims=["probe", "field"], labels=labels,
                info={"encoders": {"field": {"chrom": enc}}, "missing_code": np.nan})


def _run(cls, params):
    ctx = Ctx({"output": "out", "probe_dim": "probe", "field_dim": "field", **params})
    step = cls()
    step.name = step.definition["id"]
    step.run(ctx, [_form()])
    return ctx["out"]


def test_beta():
    from src.task.step.steps.methylation_beta_value import MethylationBetaValueStep
    out = _run(MethylationBetaValueStep, {"min_coverage": 5})
    assert out.data[0, 0] == 1.0
    assert abs(out.data[1, 0] - 0.8) < 1e-9
    assert abs(out.data[0, 2] - 1.0) < 1e-9


def test_m_value():
    from src.task.step.steps.methylation_m_value import MethylationMValueStep
    out = _run(MethylationMValueStep, {})
    assert abs(out.data[0, 0] - np.log2(11.0)) < 1e-9
    assert abs(out.data[0, 2] - 2 * np.log2(11.0)) < 1e-9


def test_dmr():
    from src.task.step.steps.dmr_window_scan import DmrWindowScanStep
    out = _run(DmrWindowScanStep, {"window_bp": 600, "min_probes": 2})
    assert out.data.shape[0] == 1
    assert out.data[0, 3] > 0
