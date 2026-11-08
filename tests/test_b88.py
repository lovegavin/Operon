import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.steps.transformer_classifier import TransformerClassifierStep
from src.task.step.steps.cnn_image_classifier import CnnImageClassifierStep
from src.task.step.steps.kernel_shap import KernelShapStep


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


def test_transformer_classifier_separates_two_classes():
    rows = [[0.0, 0.0, 0], [0.2, 0.1, 0], [0.1, 0.2, 0], [1.0, 1.0, 1], [1.2, 0.9, 1], [1.1, 1.1, 1]]
    data = form(rows, ["row", "field"],
                {"row": {f"s{i}": i for i in range(6)}, "field": {"a": 0, "b": 1, "label": 2}})
    out = run(TransformerClassifierStep(), [data], {"output": "t", "epochs": 300, "seed": 3})
    c = cols(out)
    assert out.data[0, c["accuracy"]] == 1.0
    assert out.data[0, c["n_classes"]] == 2.0
    assert out.data[0, c["n_params"]] > 0


def test_cnn_image_classifier_learns_patch_position():
    imgs = []
    for v in (0, 0, 1, 1):
        img = np.zeros((4, 4))
        if v == 0:
            img[0, 0] = 1
        else:
            img[3, 3] = 1
        imgs.append(list(img.reshape(-1)) + [float(v)])
    labels_map = {f"p{i}": 0 for i in range(4)}
    fields = {f"x{j}": j for j in range(16)}
    fields["label"] = 16
    data = form(imgs, ["row", "field"], {"row": {f"p{i}": i for i in range(4)}, "field": fields})
    out = run(CnnImageClassifierStep(), [data], {"output": "c", "height": 4, "width": 4, "epochs": 300, "seed": 5})
    c = cols(out)
    assert out.data[0, c["accuracy"]] == 1.0
    assert out.data[0, c["height"]] == 4.0
    assert out.data[0, c["width"]] == 4.0


def test_kernel_shap_matches_linear_closed_form():
    x = np.array([[0.0, 1.0], [2.0, 0.0], [1.0, 2.0], [3.0, 1.0]])
    y = 2 * x[:, 0] - 1 * x[:, 1]
    rows = np.column_stack([x, y]).tolist()
    data = form(rows, ["row", "field"],
                {"row": {f"r{i}": i for i in range(4)}, "field": {"a": 0, "b": 1, "target": 2}})
    out = run(KernelShapStep(), [data], {"output": "s", "row": 0, "alpha": 0.0})
    c = cols(out)
    phi = out.data[:, c["phi"]]
    # with alpha=0 the least-squares fit recovers y exactly; phi_j = w_j (x0_j - mean_j)
    w = np.array([2.0, -1.0])
    expected = w * (x[0] - x.mean(axis=0))
    np.testing.assert_allclose(phi, expected, atol=1e-9)
    assert abs(float(out.info["prediction"]) - float(y[0])) < 1e-9
    assert abs(float(out.info["baseline"]) - float(y.mean())) < 1e-9
    assert abs(float(phi.sum()) - (float(out.info["prediction"]) - float(out.info["baseline"]))) < 1e-9
