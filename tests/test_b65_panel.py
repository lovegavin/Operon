import numpy as np
import pandas as pd

from src.reader.readers._table_common import table_form
from src.task.step.steps.sc_spatial_neighbors import ScSpatialNeighborsStep
from src.task.step.steps.sc_spatial_domains import ScSpatialDomainsStep
from src.task.step.steps.sc_spatial_variable_genes import ScSpatialVariableGenesStep


class Ctx(dict):
    def __init__(self, **params):
        super().__init__()
        self.step_params = params


COORDS = [[0.0, 0.0], [1.0, 0.5], [-1.0, 0.2], [0.5, 3.0],
          [1.5, 3.5], [5.0, 5.0], [5.5, 5.5], [9.0, 1.0]]
NAMES = [f"c{i}" for i in range(1, 9)]
COUNTS = [[5, 6, 4, 1, 1, 2, 2, 0], [0, 1, 2, 8, 9, 1, 0, 3],
          [3, 3, 3, 3, 3, 3, 3, 3], [9, 0, 8, 0, 7, 0, 6, 0]]


def coords_form():
    df = pd.DataFrame(COORDS, columns=["x", "y"])
    return table_form(df, ["cell", "field"], labels={"field": "builtin"},
                      format_name="table", encoders_cfg={}, row_labels=NAMES)


def counts_form():
    df = pd.DataFrame(COUNTS, columns=NAMES)
    return table_form(df, ["gene", "field"], labels={"field": "builtin"},
                      format_name="table", encoders_cfg={}, row_labels=["g1", "g2", "g3", "g4"])


def test_neighbors():
    ctx = Ctx(output="out", k=3)
    ScSpatialNeighborsStep().run(ctx, [coords_form()])
    out = ctx["out"]
    w = np.asarray(out.data)
    assert w.shape == (8, 8)
    assert np.allclose(np.diag(w), 0.0)
    assert np.allclose(w, w.T)
    assert 3 <= np.count_nonzero(w[0]) <= 5
    assert np.all(w >= 0) and np.all(w <= 1)


def test_domains():
    ctx = Ctx(output="out", k=3, n_domains=2, iterations=50)
    ScSpatialDomainsStep().run(ctx, [coords_form()])
    out = ctx["out"]
    labels = np.asarray(out.data)[:, 0]
    assert set(labels.tolist()) == {0.0, 1.0}
    assert len(labels) == 8


def test_svg():
    ctx = Ctx(output="out", k=3)
    ScSpatialVariableGenesStep().run(ctx, [counts_form(), coords_form()])
    out = ctx["out"]
    d = np.asarray(out.data)
    assert d.shape == (4, 3)
    assert abs(d[2, 0]) < 1e-12
    assert np.all(d[:, 0] >= -1.0001) and np.all(d[:, 0] <= 1.0001)
