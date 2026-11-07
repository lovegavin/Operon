import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.sc_knn_graph import ScKnnGraphStep
from src.task.step.steps.sc_leiden_cluster import ScLeidenClusterStep
from src.task.step.steps.sc_pseudobulk_de import ScPseudobulkDeStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params

    def __setitem__(self, key, value):
        dict.__setitem__(self, key, value)


def _form(data, dims, labels):
    f = Form(data=np.asarray(data, float), dims=dims, labels=labels,
             info={"missing_code": np.nan})
    f.validate()
    return f


def test_knn_graph_symmetric():
    x = np.array([[0, 0], [1, 0], [0, 1], [10, 10], [11, 10], [10, 11]], float)
    f = _form(x, ["cell", "feature"], {"cell": {str(i): i for i in range(6)}, "feature": {"x": 0, "y": 1}})
    ctx = Ctx({"k": 2, "output": "graph"})
    ScKnnGraphStep().run(ctx, [f])
    g = ctx["graph"]
    assert g.data.shape == (6, 6)
    assert np.allclose(g.data, g.data.T)
    assert np.allclose(np.diag(g.data), 0)
    assert g.data[0, 1] > 0.3


def test_leiden_two_blocks():
    a = np.zeros((6, 6))
    for i in range(3):
        for j in range(3):
            if i != j:
                a[i, j] = 1.0
                a[i + 3, j + 3] = 1.0
    f = _form(a, ["cell", "cell2"], {"cell": {str(i): i for i in range(6)}, "cell2": {str(i): i for i in range(6)}})
    ctx = Ctx({"resolution": 1.0, "seed": 0, "output": "clusters"})
    ScLeidenClusterStep().run(ctx, [f])
    c = ctx["clusters"]
    assert c.info["n_clusters"] == 2
    assert len(set(c.data[:, 0])) == 2


def test_pseudobulk_de_means():
    counts = np.array([[10, 12, 11, 20, 22, 21],
                       [5, 4, 6, 1, 2, 1]], float)
    groups = np.array([[0], [0], [0], [1], [1], [1]], float)
    fc = _form(counts, ["gene", "cell"], {"gene": {"g0": 0, "g1": 1}, "cell": {str(i): i for i in range(6)}})
    fg = _form(groups, ["cell", "field"], {"cell": {str(i): i for i in range(6)}, "field": {"group": 0}})
    ctx = Ctx({"output": "de"})
    ScPseudobulkDeStep().run(ctx, [fc, fg])
    d = ctx["de"]
    assert abs(d.data[0, 0] - 11) < 1e-9
    assert abs(d.data[0, 1] - 21) < 1e-9
    assert abs(d.data[0, 2] - np.log2(22 / 12)) < 1e-9
    assert d.data[0, 5] < 0.01
