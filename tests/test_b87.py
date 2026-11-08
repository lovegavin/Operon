import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.steps.mutational_signature_decomposition import MutationalSignatureDecompositionStep
from src.task.step.steps.vae_anomaly import VaeAnomalyStep
from src.task.step.steps.deep_survival import DeepSurvivalStep


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


def test_signature_decomposition_recovers_exposures():
    counts = form([[3, 5, 0, 0], [1, 1, 0, 0]], ["sample", "channel"],
                  {"sample": {"s1": 0, "s2": 1}, "channel": {"c1": 0, "c2": 1, "c3": 2, "c4": 3}})
    sigs = form([[1, 0, 0, 0], [0, 1, 0, 0]], ["signature", "channel"],
                {"signature": {"S1": 0, "S2": 1}, "channel": {"c1": 0, "c2": 1, "c3": 2, "c4": 3}})
    out = run(MutationalSignatureDecompositionStep(), [counts, sigs], {"output": "sig"})
    names = {k: i for k, i in out.labels["statistic"].items()}
    np.testing.assert_allclose(out.data[0, names["exposure_S1"]], 3.0, atol=1e-6)
    np.testing.assert_allclose(out.data[0, names["exposure_S2"]], 5.0, atol=1e-6)
    np.testing.assert_allclose(out.data[:, names["cosine"]], [1.0, 1.0], atol=1e-6)


def test_vae_anomaly_returns_scores_and_summary():
    x = np.array([[0.0, 0.0], [0.1, 0.05], [0.05, 0.1], [5.0, 5.0], [5.1, 4.9], [0.0, 0.1]])
    data = form(x, ["sample", "feature"], {"sample": {f"s{i}": i for i in range(6)}, "feature": {"a": 0, "b": 1}})
    out = run(VaeAnomalyStep(), [data], {"output": "vae", "epochs": 200, "seed": 3})
    names = {k: i for k, i in out.labels["statistic"].items()}
    assert out.data.shape[0] == 7
    assert np.all(out.data[:6, names["recon_error"]] >= 0)
    thr = out.data[6, names["threshold"]]
    assert thr > 0
    assert 0 <= out.data[6, names["n_anomalies"]] <= 6


def test_deep_survival_scores_risk():
    rows = []
    for i, (x, t, e) in enumerate([(0.0, 1, 1), (1.0, 2, 1), (2.0, 3, 0), (3.0, 4, 1), (4.0, 5, 1), (5.0, 6, 0)]):
        rows.append([x, t, e])
    data = form(rows, ["sample", "field"], {"sample": {f"s{i}": i for i in range(6)},
                                           "field": {"x": 0, "time": 1, "event": 2}})
    out = run(DeepSurvivalStep(), [data], {"output": "surv", "epochs": 300, "seed": 5})
    names = {k: i for k, i in out.labels["statistic"].items()}
    assert out.data[0, names["n_events"]] == 4
    assert 0.0 <= out.data[0, names["c_index"]] <= 1.0
    assert np.isfinite(out.data[0, names["log_likelihood"]])
