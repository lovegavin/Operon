import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.splicing_psi import SplicingPsiStep
from src.task.step.steps.exon_skipping import ExonSkippingStep
from src.task.step.steps.intron_retention import IntronRetentionStep
from src.task.step.steps.alternative_polyadenylation import AlternativePolyadenylationStep
from src.task.step.steps.isoform_quantification_em import IsoformQuantificationEmStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self._values = self


def form(rows, row_dim, columns, label_prefix):
    data = np.asarray(rows, dtype=float)
    labels = {row_dim: {f"{label_prefix}{i}": i for i in range(data.shape[0])},
              "field": {c: i for i, c in enumerate(columns)}}
    return Form(data=data, dims=[row_dim, "field"], labels=labels,
                info={"missing_code": np.nan})


def test_psi():
    f = form([[5, 5], [9, 1], [0, 4]], "event", ["inclusion", "skipping"], "e")
    ctx = Ctx({"output": "out"})
    SplicingPsiStep().run(ctx, [f])
    out = ctx["out"]
    assert out.data.shape == (3, 4)
    assert abs(out.data[0, 0] - 0.5) < 1e-12
    assert abs(out.data[1, 0] - 0.9) < 1e-12
    assert out.data[2, 0] == 0.0
    assert out.data[0, 1] < out.data[0, 0] < out.data[0, 2]


def test_exon_skipping():
    f = form([[5, 5, 0], [9, 1, 0], [0, 4, 1]], "exon", ["inclusion", "exclusion", "gene_index"], "x")
    ctx = Ctx({"output": "out"})
    ExonSkippingStep().run(ctx, [f])
    out = ctx["out"]
    assert abs(out.data[0, 0] - 0.5) < 1e-12
    assert abs(out.data[0, 1] - 0.7) < 1e-12
    assert abs(out.data[0, 2] + 0.2) < 1e-12


def test_intron_retention():
    f = form([[10, 100, 100, 1000], [0, 100, 100, 1000]], "intron",
             ["intron_reads", "exon_reads", "intron_length", "exon_length"], "i")
    ctx = Ctx({"output": "out"})
    IntronRetentionStep().run(ctx, [f])
    out = ctx["out"]
    assert abs(out.data[0, 0] - 1.0) < 1e-12
    assert abs(out.data[1, 0]) < 1e-12


def test_apa():
    f = form([[9, 1], [5, 5], [1, 9]], "gene", ["proximal", "distal"], "g")
    ctx = Ctx({"output": "out"})
    AlternativePolyadenylationStep().run(ctx, [f])
    out = ctx["out"]
    assert abs(out.data[0, 0] - 0.9) < 1e-12
    assert out.data[0, 3] == 1.0
    assert out.data[1, 3] == 0.0


def test_isoform_em():
    compat = Form(data=np.array([[1.0, 1.0, 0.0], [0.0, 0.0, 1.0]]),
                  dims=["isoform", "exon"],
                  labels={"isoform": {"i1": 0, "i2": 1}, "exon": {"e1": 0, "e2": 1, "e3": 2}},
                  info={"missing_code": np.nan})
    counts = Form(data=np.array([[10.0], [5.0], [7.0]]), dims=["exon", "sample"],
                  labels={"exon": {"e1": 0, "e2": 1, "e3": 2}, "sample": {"s1": 0}},
                  info={"missing_code": np.nan})
    ctx = Ctx({"output": "out", "max_iter": 500, "tol": 1e-10})
    IsoformQuantificationEmStep().run(ctx, [compat, counts])
    out = ctx["out"]
    assert out.data.shape == (2, 4)
    assert abs(out.data[0, 0] - 15.0) < 1e-6
    assert abs(out.data[1, 0] - 7.0) < 1e-6
    assert abs(out.data[0, 1] - 15.0 / 22.0) < 1e-6
