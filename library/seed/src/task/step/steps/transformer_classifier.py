"""Auto-generated b88 operator: Transformer classifier."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._b88_common import matrix, labels, table


class TransformerClassifierStep(Step):
    parameters_file = "transformer_classifier.TransformerClassifierStep.parameters.json"
    definition = {'id': 'transformer_classifier', 'kind': 'operator', 'version': '1.0.0', 'title': 'Transformer classifier', 'description': 'Multi-head self-attention encoder over tabular features with a class token head. (batch b88).', 'category': 'Machine Learning', 'icon': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}, 'dependencies': ['numpy>=1.24', 'torch>=2.4,<3']}

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
        feat = [lab[k] for k, _ in sorted(lab.items(), key=lambda kv: kv[1]) if k != lc]
        xs = x[:, feat]
        n, d = xs.shape
        ncls = int(y.max()) + 1
        d_model = int(params.get("d_model", 8))
        nhead = int(params.get("nhead", 2))
        layers = int(params.get("layers", 1))
        epochs = int(params.get("epochs", 200))
        lr = float(params.get("learning_rate", 0.01))
        seed = int(params.get("seed", 7))
        torch.manual_seed(seed)
        np.random.seed(seed)

        class Net(nn.Module):
            def __init__(self):
                super().__init__()
                self.proj = nn.Linear(d, d_model)
                self.pos = nn.Parameter(torch.zeros(1, 1, d_model))
                enc = nn.TransformerEncoderLayer(d_model, nhead, dim_feedforward=2 * d_model, batch_first=True)
                self.enc = nn.TransformerEncoder(enc, layers)
                self.head = nn.Linear(d_model, ncls)

            def forward(self, z):
                h = self.proj(z).unsqueeze(1) + self.pos
                h = self.enc(h)
                return self.head(h.mean(dim=1))

        model = Net()
        opt = torch.optim.Adam(model.parameters(), lr=lr)
        xt = torch.tensor(xs, dtype=torch.float32)
        yt = torch.tensor(y, dtype=torch.long)
        for _ in range(max(1, epochs)):
            opt.zero_grad()
            loss = nn.CrossEntropyLoss()(model(xt), yt)
            loss.backward()
            opt.step()
        with torch.no_grad():
            prob = torch.softmax(model(xt), dim=1).numpy()
        pred = prob.argmax(axis=1)
        acc = float((pred == y).mean())
        ll = float(-np.log(np.clip(prob[np.arange(n), y], 1e-12, 1.0)).mean())
        nparam = int(sum(p.numel() for p in model.parameters()))
        vals = {"accuracy": [acc], "log_loss": [ll], "n_train": [float(n)], "n_classes": [float(ncls)], "n_params": [float(nparam)]}
        ctx[out_name] = table(["transformer"], vals)

