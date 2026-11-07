import numpy as np
import pytest
from src.core import Form
from src.task.context import Context
from src.task.step.steps.taxon_abundance_collapse import TaxonAbundanceCollapseStep
from src.task.step.steps.humann_pathway_collapse import HumannPathwayCollapseStep
from src.task.step.steps.metaphlan_profile_merge import MetaphlanProfileMergeStep


class Ctx(Context):
    def __init__(self, params):
        self.step_params = dict(params)
        self._values = {}

    def __getitem__(self, key):
        return self._values[key]

    def __setitem__(self, key, value):
        self._values[key] = value


def form(names, cols, data):
    labels = {"taxon": {n: i for i, n in enumerate(names)},
              "sample": {c: i for i, c in enumerate(cols)}}
    f = Form(data=np.asarray(data, float), dims=["taxon", "sample"], labels=labels, info={})
    f.validate()
    return f


def run(step, ctx, forms):
    step.name = step.definition["id"]
    step.run(ctx, forms)
    return ctx[ctx.step_params["output"]]


def test_taxon_collapse_family():
    names = ["d__B;p__P;c__C;o__O;f__F;g__G1", "d__B;p__P;c__C;o__O;f__F;g__G2",
             "d__B;p__P;c__C;o__O;f__F2;g__G3"]
    f = form(names, ["s1", "s2"], [[10, 20], [5, 7], [1, 2]])
    out = run(TaxonAbundanceCollapseStep(), Ctx({"rank": "family", "output": "o"}), [f])
    assert out.data.shape == (2, 2)
    assert out.labels["taxon"] == {"f__F": 0, "f__F2": 1}
    assert np.allclose(out.data, [[15, 27], [1, 2]])


def test_humann_collapse():
    f = form(["PWY1|g__A", "PWY1|g__B", "PWY2|g__A"], ["s1"], [[1], [3], [5]])
    out = run(HumannPathwayCollapseStep(), Ctx({"output": "o"}), [f])
    assert out.labels["taxon"] == {"PWY1": 0, "PWY2": 1}
    assert np.allclose(out.data[:, 0], [4, 5])


def test_merge_profiles():
    a = form(["t1", "t2"], ["s1", "s2"], [[1, 2], [3, 4]])
    b = form(["t2", "t3"], ["s1", "s2"], [[10, 20], [5, 6]])
    out = run(MetaphlanProfileMergeStep(), Ctx({"output": "o"}), [a, b])
    assert out.data.shape == (3, 4)
    assert out.labels["taxon"]["t2"] == 1
    assert np.allclose(out.data[1], [3, 4, 10, 20])
