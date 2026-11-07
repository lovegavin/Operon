import numpy as np
import pytest
from src.core import Form
from src.task.step.steps.sc_cnv_score import ScCnvScoreStep
from src.task.step.steps.sc_deconvolution import ScDeconvolutionStep
from src.task.step.steps.mhc_binding_motif import MhcBindingMotifStep


class Ctx:
    def __init__(self, params):
        self.step_params = params
        self.data = {}

    def __setitem__(self, k, v):
        self.data[k] = v

    def __getitem__(self, k):
        return self.data[k]


def expr_form():
    return Form(data=np.array([[1, 2, 3, 4], [2, 3, 4, 6], [5, 5, 6, 7],
                               [8, 7, 9, 9], [1, 1, 1, 2]], float), dims=["row", "field"],
                labels={"row": {f"G{i+1}": i for i in range(5)},
                        "field": {f"g{j+1}": j for j in range(4)}})


def arm_form():
    return Form(data=np.array([[0], [0], [1], [1], [0]], float), dims=["row", "field"],
                labels={"row": {f"G{i+1}": i for i in range(5)},
                        "field": {"gene": 0}})


def bulk_form():
    return Form(data=np.array([[2, 6, 10], [4, 7, 12], [9, 4, 15], [14, 11, 20], [2, 7, 9]], float),
                dims=["row", "field"],
                labels={"row": {f"G{i+1}": i for i in range(5)},
                        "field": {"gene": 0}})


def sig_form():
    return Form(data=np.array([[1, 5], [2, 6], [8, 2], [12, 3], [1, 6]], float), dims=["row", "field"],
                labels={"row": {f"G{i+1}": i for i in range(5)},
                        "field": {"gene": 0}})


def pep_form():
    vals = ["ALMFGILMV", "AAAAAAAAA", "PEPTIDE"]
    return Form(data=np.array([[0], [0], [0]], float), dims=["row", "field"],
                labels={"row": {v: i for i, v in enumerate(vals)}, "field": {"peptide": 0}})


def test_cnv_arm_abs_z():
    ctx = Ctx({"output": "cnv", "row_dim": "row", "field_dim": "field"})
    ScCnvScoreStep().run(ctx, [expr_form(), arm_form()])
    out = ctx["cnv"]
    assert out.data.shape == (4, 2)
    assert out.data[0, 0] == pytest.approx(0.97140452, rel=1e-8)
    assert out.data[1, 0] == pytest.approx(0.90824829, rel=1e-8)


def test_deconvolution_nnls_sums_to_one():
    ctx = Ctx({"output": "out", "row_dim": "row", "field_dim": "field"})
    ScDeconvolutionStep().run(ctx, [bulk_form(), sig_form()])
    out = ctx["out"]
    assert out.data.shape == (3, 2)
    assert np.allclose(out.data.sum(axis=1), 1.0)
    assert out.data[0, 0] > 0.8


def test_mhc_anchor_scores():
    ctx = Ctx({"output": "mhc", "row_dim": "row", "field_dim": "field"})
    MhcBindingMotifStep().run(ctx, [pep_form()])
    out = ctx["mhc"]
    assert out.data[0, 0] == 5.0
    assert out.data[1, 0] == 1.0
    assert out.data[2, 0] == 0.0
