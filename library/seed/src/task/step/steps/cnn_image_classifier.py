"""Auto-generated b88 operator: CNN image classifier."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._b88_common import matrix, labels, table


class CnnImageClassifierStep(Step):
    parameters_file = "cnn_image_classifier.CnnImageClassifierStep.parameters.json"
    definition = {'id': 'cnn_image_classifier', 'kind': 'operator', 'version': '1.0.0', 'title': 'CNN image classifier', 'description': 'Two-layer convolutional classifier for flattened square grayscale images. (batch b88).', 'category': 'Machine Learning', 'icon': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}, 'dependencies': ['numpy>=1.24', 'torch>=2.4,<3']}

    def run(self, ctx, inputs):
        import torch
        from torch import nn
        params = ctx.step_params
        out_name = params["output"]
        x = matrix(inputs[0])
        lab = labels(inputs[0], inputs[0].dims[1])
        lc = params.get("label_column", "label")
        if lc not in lab:
            raise ValueError(f"missing label column {lc}")
        y = x[:, lab[lc]].astype(int)
        pix = [lab[k] for k, _ in sorted(lab.items(), key=lambda kv: kv[1]) if k != lc]
        xs = x[:, pix]
        h = int(params.get("height", 4)); w = int(params.get("width", 4))
        n = xs.shape[0]
        if xs.shape[1] != h * w:
            raise ValueError(f"expected {h*w} pixels, got {xs.shape[1]}")
        ncls = int(y.max()) + 1
        epochs = int(params.get("epochs", 200)); lr = float(params.get("learning_rate", 0.01)); seed = int(params.get("seed", 7))
        torch.manual_seed(seed); np.random.seed(seed)
        img = torch.tensor(xs.reshape(n, 1, h, w), dtype=torch.float32)

        class CNN(nn.Module):
            def __init__(self):
                super().__init__()
                self.c1 = nn.Conv2d(1, 4, 3, padding=1)
                self.c2 = nn.Conv2d(4, 8, 3, padding=1)
                self.pool = nn.AdaptiveAvgPool2d(1)
                self.head = nn.Linear(8, ncls)

            def forward(self, z):
                z = torch.relu(self.c1(z))
                z = torch.relu(self.c2(z))
                return self.head(self.pool(z).flatten(1))

        model = CNN(); opt = torch.optim.Adam(model.parameters(), lr=lr)
        yt = torch.tensor(y, dtype=torch.long)
        for _ in range(max(1, epochs)):
            opt.zero_grad(); loss = nn.CrossEntropyLoss()(model(img), yt); loss.backward(); opt.step()
        with torch.no_grad():
            prob = torch.softmax(model(img), dim=1).numpy()
        pred = prob.argmax(axis=1)
        acc = float((pred == y).mean())
        ll = float(-np.log(np.clip(prob[np.arange(n), y], 1e-12, 1.0)).mean())
        nparam = int(sum(p.numel() for p in model.parameters()))
        vals = {"accuracy": [acc], "log_loss": [ll], "n_train": [float(n)], "n_classes": [float(ncls)], "n_params": [float(nparam)], "height": [float(h)], "width": [float(w)]}
        ctx[out_name] = table(["cnn"], vals)

