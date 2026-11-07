import numpy as np
from src.core import Form
from src.task.step.steps.circrna_detect import CircrnaDetectStep
from src.task.step.steps.rna_editing_detect import RnaEditingDetectStep
from src.task.step.steps.motif_discovery_em import MotifDiscoveryEmStep


class Ctx(dict):
    pass


def table(rows, cols, names, enc=None):
    f = Form(data=np.asarray(rows, dtype=float), dims=["row", "field"],
             labels={"row": {n: i for i, n in enumerate(names)},
                     "field": {c: i for i, c in enumerate(cols)}},
             info={"encoders": {"field": enc or {}}})
    return f


def run(step, inputs, **params):
    c = Ctx()
    c.step_params = {"output": "out", **params}
    step.run(c, inputs)
    return c["out"]


def test_circ():
    enc = {"chrom": {"chr1": 0, "chr2": 1}}
    f = table([[0, 500, 200, 10], [0, 100, 400, 5]], ["chrom", "donor", "acceptor", "count"], ["j1", "j2"], enc)
    out = run(CircrnaDetectStep(), [f])
    assert out.data[0, 0] == 1 and out.data[0, 1] == 301
    assert out.data[1, 0] == 0


def test_edit():
    enc = {"chrom": {"chr1": 0}, "ref": {"A": 0, "T": 1}, "alt": {"G": 0, "C": 1}}
    f = table([[0, 100, 0, 0, 10, 4], [0, 200, 1, 1, 8, 3]], ["chrom", "pos", "ref", "alt", "coverage", "alt_count"], ["v1", "v2"], enc)
    out = run(RnaEditingDetectStep(), [f])
    assert out.data[0, 0] == 1 and abs(out.data[0, 1] - 0.4) < 1e-9
    assert out.data[1, 0] == 1 and abs(out.data[1, 1] - 0.375) < 1e-9


def test_motif():
    f = Form(data=np.asarray([[0], [1]]), dims=["row", "field"],
             labels={"row": {"s1": 0, "s2": 1}, "field": {"seq": 0}},
             info={"encoders": {"field": {"seq": {"ACGTAC": 0, "ACGTTC": 1}}}})
    out = run(MotifDiscoveryEmStep(), [f], width=6)
    assert out.data.shape == (6, 4)
    assert abs(out.data[0, 0] - 0.5) < 1e-9
