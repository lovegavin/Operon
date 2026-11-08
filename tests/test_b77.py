import math

import numpy as np
import pytest

from src.core import Form
from src.core.errors import StepError
from src.task.step.steps.proteomics_ibaq import ProteomicsIbaqStep
from src.task.step.steps.ptm_occupancy import PtmOccupancyStep
from src.task.step.steps.sequence_cai import SequenceCaiStep


class Enc:
    def __init__(self, inverse):
        self.inverse = inverse


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def form(dims, labels, data, encoders=None):
    info = {"encoders": encoders} if encoders else {}
    out = Form(data=np.asarray(data, dtype=np.float64), dims=list(dims), labels=labels, info=info)
    out.validate()
    return out


def peptides_form():
    labels = {"row": {str(i): i for i in range(5)},
              "field": {"protein": 0, "peptide": 1, "intensity": 2}}
    enc = {"field": {"protein": Enc({0: "P1", 1: "P2"}),
                     "peptide": Enc({0: "AAK", 1: "GGK", 2: "TTK"})}}
    return form(["row", "field"], labels,
                [[0, 0, 100], [0, 0, 50], [0, 1, 50], [1, 0, 200], [1, 0, 20]], enc)


def cds_form():
    labels = {"seq": {"S1": 0, "S2": 1}, "field": {"seq": 0}}
    enc = {"field": {"seq": Enc({0: "ATGGCTTAA", 1: "ATGAAATGA"})}}
    return form(["seq", "field"], labels, [[0], [1]], enc)


def weights_form():
    labels = {"codon": {"ATG": 0, "GCT": 1, "AAA": 2, "TAA": 3},
              "field": {"codon": 0, "w": 1}}
    enc = {"field": {"codon": Enc({0: "ATG", 1: "GCT", 2: "AAA", 3: "TAA"})}}
    return form(["codon", "field"], labels, [[0, 0.8], [1, 0.5], [2, 0.4], [3, 1.0]], enc)


def ptm_form():
    labels = {"site": {"S1": 0, "S2": 1, "S3": 2},
              "field": {"modified": 0, "unmodified": 1}}
    return form(["site", "field"], labels, [[80, 20], [0, 50], [0, 0]])


def test_ibaq_distinct_peptides():
    ctx = Ctx({"row_dim": "row", "field_dim": "field", "output": "ibaq"})
    ProteomicsIbaqStep().run(ctx, [peptides_form()])
    out = ctx["ibaq"]
    assert out.data.shape == (2, 3)
    assert out.data[0].tolist() == [2.0, 200.0, 100.0]
    assert out.data[1].tolist() == [1.0, 220.0, 220.0]


def test_cai_geometric_mean():
    ctx = Ctx({"seq_dim": "seq", "codon_dim": "codon", "field_dim": "field", "output": "cai"})
    SequenceCaiStep().run(ctx, [cds_form(), weights_form()])
    out = ctx["cai"]
    assert out.data[0, 0] == 3.0 and out.data[0, 1] == 2.0
    assert out.data[0, 2] == pytest.approx(math.sqrt(0.8 * 0.5), rel=1e-9)
    assert out.data[1, 2] == pytest.approx(math.sqrt(0.8 * 0.4), rel=1e-9)


def test_ptm_occupancy_and_nan():
    ctx = Ctx({"row_dim": "site", "field_dim": "field", "output": "occupancy"})
    PtmOccupancyStep().run(ctx, [ptm_form()])
    out = ctx["occupancy"]
    assert out.data[0, 2] == pytest.approx(0.8)
    assert out.data[1, 2] == pytest.approx(0.0)
    assert np.isnan(out.data[2, 2])


def test_ibaq_rejects_negative_intensity():
    bad = form(["row", "field"],
               {"row": {"0": 0}, "field": {"protein": 0, "peptide": 1, "intensity": 2}},
               [[0, 0, -5]],
               {"field": {"protein": Enc({0: "P1"}), "peptide": Enc({0: "AA"})}})
    ctx = Ctx({"row_dim": "row", "field_dim": "field", "output": "ibaq"})
    with pytest.raises(StepError):
        ProteomicsIbaqStep().run(ctx, [bad])
