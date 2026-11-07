import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "library" / "seed"))
import numpy as np
from src.core import Form
from src.core.encoding import LabelEncoder
from src.task.context import Context
from src.task.step.steps.spectral_entropy import SpectralEntropyStep
from src.task.step.steps.ms2_cosine_similarity import Ms2CosineSimilarityStep
from src.task.step.steps.ptm_localization_score import PtmLocalizationScoreStep
from src.task.step.steps.epitope_conservation import EpitopeConservationStep
from src.task.step.steps.mhc_anchor_score import MhcAnchorScoreStep


class Ctx(Context):
    def __init__(self, params):
        self.step_params = params
        self._values = {}
        self.name = "test"

    def __setitem__(self, key, value):
        self._values[key] = value

    def __getitem__(self, key):
        return self._values[key]


def codes(values, col):
    enc = LabelEncoder()
    data = enc.fit_transform(values)
    return data, {col: enc}


def table_form(rows, columns, data, encoders=None):
    return Form(
        data=np.asarray(data, dtype=float),
        dims=["row", "field"],
        labels={"row": {str(r): i for i, r in enumerate(rows)},
                "field": {c: i for i, c in enumerate(columns)}},
        info={"encoders": {"field": encoders or {}}, "missing_code": np.nan},
    )


def run(step, form, params):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return ctx[params["output"]]


def test_spectral_entropy():
    data, enc = codes(["s1"] * 3, "spectrum")
    form = table_form(["p1", "p2", "p3"], ["spectrum", "mz", "intensity"],
                      np.column_stack([data, [100, 200, 300], [1, 1, 1]]), enc)
    out = run(SpectralEntropyStep(), form, {"output": "o"})
    assert out.data.shape == (1, 4)
    assert abs(out.data[0, 1] - np.log2(3)) < 1e-9
    assert abs(out.data[0, 2] - 1.0) < 1e-9


def test_ms2_cosine():
    qd, qenc = codes(["q", "q"], "spectrum")
    q = table_form(["p1", "p2"], ["spectrum", "mz", "intensity"],
                   np.column_stack([qd, [100, 200], [1, 0.5]]), qenc)
    ld, lenc = codes(["l", "l"], "spectrum")
    lib = table_form(["l1", "l2"], ["spectrum", "mz", "intensity"],
                     np.column_stack([ld, [100, 200], [1, 0.5]]), lenc)
    ctx = Ctx({"output": "o"})
    Ms2CosineSimilarityStep().run(ctx, [q, lib])
    out = ctx["o"]
    assert out.data.shape == (1, 3)
    assert abs(out.data[0, 0] - 1.0) < 1e-9
    assert out.data[0, 1] == 2


def test_ptm():
    data, enc = codes(["a", "b"], "psm")
    form = table_form(["r1", "r2"], ["psm", "delta_score", "n_candidates"],
                      np.column_stack([data, [10, 30], [2, 2]]), enc)
    out = run(PtmLocalizationScoreStep(), form, {"output": "o"})
    assert abs(out.data[0, 0] - 10 / 11) < 1e-9
    assert out.data[1, 1] == 1.0


def test_epitope():
    data, enc = codes(["AC", "AC", "AV"], "sequence")
    form = table_form(["e1", "e2", "e3"], ["sequence"], data.reshape(-1, 1), enc)
    out = run(EpitopeConservationStep(), form, {"output": "o"})
    assert out.data.shape == (2, 4)
    assert abs(out.data[0, 0]) < 1e-9
    assert out.data[1, 0] > 0


def test_mhc():
    data, enc = codes(["LLAAAAAAL", "AAAAAAAAA"], "sequence")
    form = table_form(["p1", "p2"], ["sequence"], data.reshape(-1, 1), enc)
    out = run(MhcAnchorScoreStep(), form, {"output": "o"})
    assert out.data[0, 0] == 2.0
    assert out.data[1, 0] == 0.0
