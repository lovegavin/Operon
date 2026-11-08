"""Train a small MLP classifier

Fits a two-layer perceptron (torch) on a labelled feature table and reports training accuracy and cross-entropy loss.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step
from src.task.step.steps._b85_common import matrix, named_column, table

class MlpClassifierStep(Step):
    parameters_file = "mlp_classifier.MlpClassifierStep.parameters.json"
    definition = {'protocol_version': 3, 'protocol_revision': '3.7', 'kind': 'operator', 'id': 'mlp_classifier', 'version': '1.0.0', 'title': 'Train a small MLP classifier', 'description': 'Fits a two-layer perceptron (torch) on a labelled feature table and reports training accuracy and cross-entropy loss.', 'category': 'Machine Learning', 'icon': 'brain', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}, 'dependencies': ['numpy>=1.24', 'torch>=2.4,<3'], 'dependency_imports': ['torch']}

    def run(self, ctx, inputs):
        hidden = int(ctx.step_params.get("hidden", 12))
        epochs = int(ctx.step_params.get("epochs", 200))
        learning_rate = float(ctx.step_params.get("learning_rate", 0.05))
        seed = int(ctx.step_params.get("seed", 7))
        data = matrix(inputs[0])
        labels = named_column(inputs[0], "label")
        feature_cols = [c for c in inputs[0].labels.get(inputs[0].dims[1], {}) if c != "label"]
        if not feature_cols:
            raise StepError("the table needs at least one feature column")
        cols = [int(inputs[0].labels[inputs[0].dims[1]][c]) for c in feature_cols]
        x = data[:, cols]
        y = labels.astype(int)
        if int(y.max()) > 1 or int(y.min()) < 0:
            raise StepError("label column must be 0/1")
        try:
            import torch
            from torch import nn
        except ImportError as error:
            raise StepError("torch is required for mlp_classifier") from error
        torch.manual_seed(seed)
        torch.set_num_threads(1)
        xt = torch.tensor(x, dtype=torch.float32)
        yt = torch.tensor(y, dtype=torch.long)
        net = nn.Sequential(nn.Linear(x.shape[1], hidden), nn.ReLU(), nn.Linear(hidden, 2))
        opt = torch.optim.Adam(net.parameters(), lr=learning_rate)
        loss_fn = nn.CrossEntropyLoss()
        for _ in range(epochs):
            opt.zero_grad()
            loss = loss_fn(net(xt), yt)
            loss.backward()
            opt.step()
        with torch.no_grad():
            logits = net(xt)
            probs = torch.softmax(logits, dim=1)[:, 1].numpy()
            accuracy = float(((probs >= 0.5).astype(int) == y).mean())
            log_loss = float(loss.item())
        n_params = int(sum(p.numel() for p in net.parameters()))
        out = table([[accuracy, log_loss, float(len(y)), 2.0, float(n_params)]],
                    ["accuracy", "log_loss", "n_train", "n_classes", "n_params"])
        ctx[ctx.step_params["output"]] = out

