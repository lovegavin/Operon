import numpy as np

from src.core import Form
from src.task.step.steps.image_connected_components import ImageConnectedComponentsStep
from src.task.step.steps.image_histogram_equalization import ImageHistogramEqualizationStep
from src.task.step.steps.image_otsu_threshold import ImageOtsuThresholdStep
from src.task.step.steps.image_sobel_gradient import ImageSobelGradientStep
from src.task.step.steps.ml_partial_dependence import MlPartialDependenceStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def image_form(data):
    return Form(np.asarray(data, dtype=float), dims=["y", "x"],
                labels={"y": {str(i): i for i in range(len(data))},
                        "x": {str(j): j for j in range(len(data[0]))}})


def test_otsu_bimodal():
    img = [[0.0] * 3 + [255.0] * 3 for _ in range(4)]
    ctx = Ctx({"output": "out"})
    ImageOtsuThresholdStep().run(ctx, [image_form(img)])
    out = ctx["out"]
    thr = out.data[0, 0]
    assert 100.0 < thr < 160.0
    assert abs(out.data[0, 2] - 0.5) < 1e-9


def test_components_two_blobs():
    img = [[1, 1, 0, 0], [1, 1, 0, 1], [0, 0, 0, 1], [0, 0, 0, 0]]
    ctx = Ctx({"output": "out", "min_area": 1})
    ImageConnectedComponentsStep().run(ctx, [image_form(img)])
    out = ctx["out"]
    assert out.data.shape[1] == 8
    areas = sorted(out.data[:, 1].tolist())
    assert areas == [2.0, 4.0]


def test_equalization_monotone():
    img = [[0.0, 0.0], [100.0, 200.0]]
    ctx = Ctx({"output": "out"})
    ImageHistogramEqualizationStep().run(ctx, [image_form(img)])
    out = ctx["out"]
    assert np.all(out.data >= 0.0) and np.all(out.data <= 1.0)
    assert out.data[0, 0] <= out.data[1, 0] <= out.data[1, 1]


def test_sobel_vertical_edge():
    img = [[0.0, 0.0, 10.0, 10.0] for _ in range(4)]
    ctx = Ctx({"output": "out"})
    ImageSobelGradientStep().run(ctx, [image_form(img)])
    out = ctx["out"]
    assert out.data[0, 0] == 0.0 and out.data[3, 3] == 0.0
    assert out.data[1, 1] > 0.0


def test_partial_dependence_linear():
    x = np.array([[0.0], [1.0], [2.0], [3.0]])
    y = 2.0 * x
    ctx = Ctx({"output": "out", "feature": 0, "alpha": 1e-9, "n_grid": 4})
    f1 = Form(x, dims=["row", "field"], labels={"row": {str(i): i for i in range(4)}, "field": {"x": 0}})
    f2 = Form(y.reshape(-1, 1), dims=["row", "value"], labels={"row": {str(i): i for i in range(4)}, "value": {"y": 0}})
    MlPartialDependenceStep().run(ctx, [f1, f2])
    out = ctx["out"]
    vals = out.data[:, 0]
    preds = out.data[:, 1]
    assert np.allclose(vals, [0.0, 1.0, 2.0, 3.0])
    assert np.allclose(preds, 2.0 * vals, atol=1e-6)
