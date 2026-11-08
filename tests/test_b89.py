import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.steps.gcn_node_classifier import GcnNodeClassifierStep
from src.task.step.steps.deep_quantile_regressor import DeepQuantileRegressorStep
from src.task.step.steps.normalizing_flow_density import NormalizingFlowDensityStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def form(data, dims, labels):
    return Form(data=np.asarray(data, dtype=float), dims=dims, labels=labels, info={})


def run(step, inputs, params):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params["output"]]


def cols(out):
    return {k: i for k, i in out.labels["statistic"].items()}


def test_gcn_separates_two_communities():
    rows = []
    labels = [0, 0, 0, 0, 1, 1, 1, 1]
    for i, lab in enumerate(labels):
        base = 0.0 if lab == 0 else 2.0
        rows.append([base + 0.1 * i, base, lab])
    data = form(rows, ["node", "feature"],
                {"node": {f"n{i}": i for i in range(8)}, "feature": {"a": 0, "b": 1, "label": 2}})
    edges = []
    for i in range(4):
        for j in range(i + 1, 4):
            edges.append([i, j])
    for i in range(4, 8):
        for j in range(i + 1, 8):
            edges.append([i, j])
    e = form(edges, ["edge", "slot"], {"edge": {f"e{i}": i for i in range(len(edges))}, "slot": {"u": 0, "v": 1}})
    out = run(GcnNodeClassifierStep(), [data, e], {"output": "g", "label_column": "label", "hidden": 8, "epochs": 300, "learning_rate": 0.05, "seed": 1})
    c = cols(out)
    assert out.data[0, c["accuracy"]] == 1.0
    assert out.data[0, c["n_nodes"]] == 8.0
    assert out.data[0, c["n_edges"]] == float(len(edges))


def test_quantile_regressor_recovers_median_line():
    xs = np.arange(10, dtype=float)
    ys = 2.0 * xs + 1.0
    data = form(np.column_stack([xs, ys]), ["row", "field"],
                {"row": {f"r{i}": i for i in range(10)}, "field": {"x": 0, "y": 1}})
    out = run(DeepQuantileRegressorStep(), [data], {"output": "q", "feature_column": "x", "target_column": "y", "quantile": 0.5, "epochs": 800, "learning_rate": 0.05, "seed": 0})
    c = cols(out)
    assert abs(out.data[0, c["slope"]] - 2.0) < 0.05
    assert abs(out.data[0, c["intercept"]] - 1.0) < 0.2
    assert out.data[0, c["pinball_loss"]] < 0.05


def test_flow_latent_is_standard_normal():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(200, 2))
    x[:, 1] = 0.8 * x[:, 0] + 0.6 * x[:, 1]
    data = form(x, ["row", "field"], {"row": {str(i): i for i in range(200)}, "field": {"a": 0, "b": 1}})
    out = run(NormalizingFlowDensityStep(), [data], {"output": "f", "layers": 2, "hidden": 8, "epochs": 200, "learning_rate": 0.05, "seed": 0})
    c = cols(out)
    assert np.isfinite(out.data[0, c["log_likelihood"]])
    assert abs(out.data[0, c["latent_mean"]]) < 0.2
    assert abs(out.data[0, c["latent_std"]] - 1.0) < 0.2
    assert abs(out.data[0, c["latent_corr"]]) < 0.3
