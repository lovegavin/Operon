import numpy as np

from src.core.forms.form import Form
from src.task.step.steps.changepoint_pelt import ChangepointPeltStep
from src.task.step.steps.conformal_classification_sets import ConformalClassificationSetsStep
from src.task.step.steps.conformal_split_regression import ConformalSplitRegressionStep
from src.task.step.steps.hidden_markov_viterbi import HiddenMarkovViterbiStep
from src.task.step.steps.kalman_local_level import KalmanLocalLevelStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)


def table(rows, columns, names=None):
    names = names or [f"r{i}" for i in range(len(rows))]
    form = Form(
        data=np.asarray(rows, dtype=float),
        dims=["row", "field"],
        labels={"row": {name: i for i, name in enumerate(names)}, "field": {c: i for i, c in enumerate(columns)}},
        info={"format": "table"},
    )
    form.validate()
    return form


def out(form):
    return np.asarray(form.data, dtype=float)


def test_conformal_regression_interval():
    form = table(
        [[1.0, 1.1, 0], [2.0, 1.9, 0], [3.0, 3.2, 0], [4.0, 4.1, 0], [10.0, 9.9, 1]],
        ["y", "pred", "phase"],
    )
    ctx = Ctx({"alpha": 0.5, "output": "out"})
    ConformalSplitRegressionStep().run(ctx, [form])
    data = out(ctx["out"])
    assert data.shape == (1, 6)
    assert abs(data[0, 4] - 0.4) < 1e-9
    assert data[0, 5] == 1.0


def test_conformal_classification_set():
    form = table(
        [[1, 0.9, 0], [0, 0.2, 0], [1, 0.8, 0], [0, 0.3, 0], [1, 0.75, 1], [0, 0.1, 1]],
        ["y", "score", "phase"],
    )
    ctx = Ctx({"alpha": 0.5, "output": "out"})
    ConformalClassificationSetsStep().run(ctx, [form])
    data = out(ctx["out"])
    assert data.shape == (2, 6)
    assert abs(data[0, 2] - 0.7) < 1e-9
    assert data[0, 3] == 1.0 and data[0, 5] == 1.0
    assert data[1, 3] == 1.0 and data[1, 5] == 1.0


def test_changepoint_segments():
    series = [1, 1, 1, 1, 5, 5, 5, 5]
    form = table([[i, v] for i, v in enumerate(series)], ["t", "value"])
    ctx = Ctx({"penalty": 1.0, "min_size": 2, "output": "out"})
    ChangepointPeltStep().run(ctx, [form])
    data = out(ctx["out"])
    assert data.shape[0] == 2
    assert data[0, 0] == 0.0 and data[0, 1] == 4.0 and abs(data[0, 3] - 1.0) < 1e-9
    assert data[1, 0] == 4.0 and data[1, 1] == 8.0 and abs(data[1, 3] - 5.0) < 1e-9


def test_hmm_viterbi_path():
    obs = table([[0, 0], [1, 1], [2, 0]], ["t", "obs"])
    trans = table([[0.9, 0.1], [0.1, 0.9]], ["s0", "s1"], names=["s0", "s1"])
    emit = table([[0.9, 0.0], [0.0, 0.9]], ["o0", "o1"], names=["s0", "s1"])
    ctx = Ctx({"output": "out"})
    HiddenMarkovViterbiStep().run(ctx, [obs, trans, emit])
    data = out(ctx["out"])
    assert list(data[:, 1]) == [0.0, 1.0, 0.0]


def test_kalman_local_level():
    form = table([[i, 5.0] for i in range(4)], ["t", "value"])
    ctx = Ctx({"process_variance": 0.1, "observation_variance": 0.1, "output": "out"})
    KalmanLocalLevelStep().run(ctx, [form])
    data = out(ctx["out"])
    assert data.shape == (4, 6)
    assert abs(data[0, 3] - (1.1 / 1.2) * 0.1) < 1e-9  # filtered variance (1-K)*1.1
    assert abs(data[0, 5] - (1.1 / 1.2)) < 1e-9  # gain
    assert abs(data[-1, 2] - 5.0) < 1e-6
