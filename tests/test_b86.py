import numpy as np

from src.core import Form
from src.task.step.steps.hmm_baum_welch import HmmBaumWelchStep
from src.task.step.steps.kalman_smoother import KalmanSmootherStep
from src.task.step.steps.particle_filter_bootstrap import ParticleFilterBootstrapStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def form(values, dims=("row", "field")):
    data = np.asarray(values, dtype=float)
    if data.ndim == 1:
        data = data.reshape(-1, 1)
    return Form(data=data, dims=list(dims), labels={dims[0]: {str(i): i for i in range(data.shape[0])}, dims[1]: {"value": 0}})


def run(step, values, params):
    ctx = Ctx({"output": "out", **params})
    step.run(ctx, [form(values)])
    return ctx["out"]


def test_baum_welch_recovers_alternating_states():
    values = np.array([[0], [1], [0], [1], [0], [1], [0], [1]], dtype=float)
    out = run(HmmBaumWelchStep(), values, {"n_states": 2, "n_iter": 50, "tol": 1e-8, "seed": 0})
    assert out.data.shape == (1, 5)
    assert out.data[0, 2] == 1.0
    assert out.data[0, 1] >= 1
    assert out.data[0, 4] == 8
    assert np.asarray(out.info["transition"]).shape == (2, 2)


def test_kalman_smoother_matches_closed_form():
    out = run(KalmanSmootherStep(), np.array([[1.0], [2.0], [3.0]]), {"process_var": 1.0, "obs_var": 1.0})
    names = {name: i for name, i in out.labels["statistic"].items()}
    smoothed = out.data[:, names["smoothed_mean"]]
    filtered = out.data[:, names["filtered_mean"]]
    np.testing.assert_allclose(filtered, [1.0, 1.6, 2.4615385], atol=1e-6)
    np.testing.assert_allclose(smoothed, [1.3076923, 1.9230769, 2.4615385], atol=1e-6)
    sv = out.data[:, names["smoothed_var"]]; fv = out.data[:, names["filtered_var"]]
    assert sv[0] < fv[0]
    assert np.all(sv <= fv + 1e-9)


def test_particle_filter_tracks_zero():
    out = run(ParticleFilterBootstrapStep(), np.array([[0.0], [0.0], [0.0]]), {"n_particles": 500, "process_var": 0.1, "obs_var": 0.1, "seed": 3})
    means = out.data[:, 2]
    assert np.all(np.abs(means) < 0.2)
    assert out.info["log_likelihood"] < 0
