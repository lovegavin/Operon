import numpy as np

from src.core import Form
from src.task.step.steps.bayesian_linear_regression import BayesianLinearRegressionStep
from src.task.step.steps.graph_pseudotime import GraphPseudotimeStep
from src.task.step.steps.image_gaussian_blur import ImageGaussianBlurStep


class Ctx(dict):
    def __init__(self, **params):
        super().__init__()
        self.step_params = params


def frame(data, cols, rows=None):
    data = np.asarray(data, dtype=float)
    rows = rows or [str(i) for i in range(data.shape[0])]
    return Form(data=data, dims=["row", "field"],
                labels={"row": {r: i for i, r in enumerate(rows)},
                        "field": {c: i for i, c in enumerate(cols)}})


def test_bayesian_regression_matches_ols():
    rng = np.random.default_rng(2)
    n = 200
    x = rng.normal(size=n)
    y = 1.5 + 2.2 * x + rng.normal(scale=0.5, size=n)
    form = frame(np.column_stack([y, x]), ["y", "x"])
    ctx = Ctx(output="o", y_column="y", covariate_columns="x", n_samples=800, burn_in=200, seed=3)
    BayesianLinearRegressionStep().run(ctx, [form])
    out = ctx["o"]
    mean = out.data[:, out.labels["statistic"]["mean"]]
    X = np.column_stack([np.ones(n), x])
    ols = np.linalg.lstsq(X, y, rcond=None)[0]
    assert np.max(np.abs(mean - ols)) < 0.1
    names = sorted(out.labels["param"], key=lambda k: out.labels["param"][k])
    assert names[0] == "(Intercept)"


def test_graph_pseudotime_orders_trajectory():
    rng = np.random.default_rng(4)
    n = 60
    t = np.linspace(0, 1, n)
    g1 = 3 * t + rng.normal(scale=0.05, size=n)
    g2 = np.sin(2 * np.pi * t) + rng.normal(scale=0.05, size=n)
    g3 = rng.normal(scale=0.3, size=n)
    form = frame(np.column_stack([g1, g2, g3]), ["g1", "g2", "g3"])
    ctx = Ctx(output="o", n_components=3, n_neighbors=8, root_cell=0)
    GraphPseudotimeStep().run(ctx, [form])
    out = ctx["o"]
    pt = out.data[:, out.labels["statistic"]["pseudotime"]]
    assert pt.min() == 0.0 and pt.max() == 1.0
    assert np.corrcoef(pt, t)[0, 1] > 0.8


def test_image_blur_matches_scipy():
    rng = np.random.default_rng(6)
    img = rng.random((24, 20))
    form = Form(data=img, dims=["y", "x"],
                labels={"y": {str(i): i for i in range(24)}, "x": {str(j): j for j in range(20)}})
    ctx = Ctx(output="o", sigma=1.2, truncate=4.0)
    ImageGaussianBlurStep().run(ctx, [form])
    from scipy.ndimage import gaussian_filter
    assert np.max(np.abs(ctx["o"].data - gaussian_filter(img, 1.2, mode="reflect"))) < 1e-9
    const = Form(data=np.ones((8, 8)), dims=["y", "x"], labels={"y": {}, "x": {}})
    ctx2 = Ctx(output="o", sigma=2.0, truncate=4.0)
    ImageGaussianBlurStep().run(ctx2, [const])
    assert np.allclose(ctx2["o"].data, 1.0)
