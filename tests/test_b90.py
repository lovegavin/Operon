import numpy as np

from src.core import Form
from src.task.step.steps.lightgbm_classifier import LightgbmClassifierStep
from src.task.step.steps.xgboost_regressor import XgboostRegressorStep
from src.task.step.steps.hdbscan_cluster import HdbscanClusterStep


class Ctx(dict):
    @property
    def step_params(self):
        return self


def labelled(rows, columns):
    data = np.asarray(rows, dtype=float)
    return Form(data=data, dims=["row", "field"],
                labels={"row": {str(i): i for i in range(len(rows))},
                        "field": {c: i for i, c in enumerate(columns)}})


def test_lightgbm_separable():
    rows = [[0, 0.0, 0.1], [0, 0.2, -0.1], [0, -0.1, 0.05], [0, 0.1, 0.0],
            [1, 3.0, 3.1], [1, 3.2, 2.9], [1, 2.9, 3.05], [1, 3.1, 3.0]]
    form = labelled(rows, ["label", "f1", "f2"])
    ctx = Ctx(output="lightgbm", row_dim="row", field_dim="field",
              label_column="label", n_estimators=20)
    LightgbmClassifierStep().run(ctx, [form])
    out = ctx["lightgbm"]
    assert out.data.shape == (1, 6)
    assert out.data[0, 0] == 1.0


def test_xgboost_regression():
    x = np.arange(8, dtype=float)
    rows = np.column_stack([2.0 * x + 1.0, x])
    form = labelled(rows, ["target", "x"])
    ctx = Ctx(output="xgboost", row_dim="row", field_dim="field",
              target_column="target", n_estimators=30)
    XgboostRegressorStep().run(ctx, [form])
    out = ctx["xgboost"]
    assert out.data[0, 0] < 0.6
    assert out.data[0, 3] == 8.0


def test_hdbscan_two_dense_clusters():
    rows = [[0.0, 0.0], [0.05, 0.0], [0.0, 0.05], [0.05, 0.05],
            [5.0, 5.0], [5.05, 5.0], [5.0, 5.05], [5.05, 5.05]]
    form = labelled(rows, ["x", "y"])
    ctx = Ctx(output="hdbscan", row_dim="row", field_dim="field",
              min_cluster_size=2, min_samples=1)
    HdbscanClusterStep().run(ctx, [form])
    out = ctx["hdbscan"]
    labels = out.data[:, 0]
    assert len(set(labels[:4])) == 1 and len(set(labels[4:])) == 1
    assert labels[0] != labels[4]
    assert out.info["n_clusters"] == 2
