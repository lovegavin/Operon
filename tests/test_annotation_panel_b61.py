import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.steps.annotation_completeness import AnnotationCompletenessStep
from src.task.step.steps.annotation_gene_length import AnnotationGeneLengthStep
from src.task.step.steps.annotation_overlap_check import AnnotationOverlapCheckStep
from src.task.step.steps.interpro_domain_summary import InterproDomainSummaryStep
from src.task.step.steps.pfam_architecture import PfamArchitectureStep


class Ctx(Context):
    def __init__(self, params):
        self.step_params = params
        self._values = {}

    def __setitem__(self, key, value):
        self._values[key] = value

    def __getitem__(self, key):
        return self._values[key]


def form(rows, cols, row_dim, values):
    names = list(rows)
    data = np.asarray(values, dtype=float)
    labels = {row_dim: {n: i for i, n in enumerate(names)},
              "field": {c: i for i, c in enumerate(cols)}}
    return Form(data=data, dims=[row_dim, "field"], labels=labels,
                info={"missing_code": np.nan})


def run(step, params, f):
    ctx = Ctx(params)
    step.run(ctx, [f])
    return ctx[params["output"]]


def column(out, name):
    return out.data[:, out.labels["statistic"][name]]


def gene_form():
    return form(["g1", "g2", "g3"], ["start", "end"],
                "gene", [[100, 400], [200, 500], [1000, 1200]])


def domain_form():
    return form(["h1", "h2", "h3"], ["protein", "domain", "start", "end", "evalue"],
                "hit", [[1, 7, 10, 50, 1e-10], [1, 7, 40, 80, 1e-5],
                        [1, 9, 100, 120, 1e-3]])


def genome_form():
    return form(["m1", "m2", "m3"], ["genome", "present", "copies"],
                "observation", [[1, 1, 1], [1, 0, 0], [1, 1, 2]])


def test_gene_length():
    out = run(AnnotationGeneLengthStep(), {"output": "o", "short_bp": 250, "long_bp": 280},
              gene_form())
    assert np.allclose(column(out, "length_bp"), [300, 300, 200])
    assert np.allclose(column(out, "is_short"), [0, 0, 1])
    assert np.allclose(column(out, "is_long"), [1, 1, 0])


def test_overlap():
    out = run(AnnotationOverlapCheckStep(), {"output": "o"}, gene_form())
    assert np.allclose(column(out, "n_overlaps"), [1, 1, 0])
    assert np.allclose(column(out, "overlap_bp"), [200, 200, 0])
    assert np.allclose(column(out, "frac_overlapped"), [200 / 300, 200 / 300, 0])


def test_domain_summary():
    out = run(InterproDomainSummaryStep(), {"output": "o"}, domain_form())
    assert out.data.shape == (1, 4)
    assert np.allclose(out.data[0], [3, 90, 100 / 3, 10])


def test_architecture():
    out = run(PfamArchitectureStep(), {"output": "o"}, domain_form())
    assert np.allclose(out.data[0, :3], [3, 2, 1])
    assert out.info["architecture"]["1"] == "7-7-9"


def test_completeness():
    out = run(AnnotationCompletenessStep(), {"output": "o"}, genome_form())
    assert np.allclose(out.data[0], [2 / 3, 1, 1])
