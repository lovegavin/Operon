"""Score rows with a bottleneck autoencoder

Trains a small autoencoder (torch) and reports reconstruction-error statistics plus a mean+3sd anomaly threshold.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step
from src.task.step.steps._b85_common import matrix, named_column, table

class AutoencoderAnomalyStep(Step):
    parameters_file = "autoencoder_anomaly.AutoencoderAnomalyStep.parameters.json"
    definition = {'protocol_version': 3, 'protocol_revision': '3.7', 'kind': 'operator', 'id': 'autoencoder_anomaly', 'version': '1.0.0', 'title': 'Score rows with a bottleneck autoencoder', 'description': 'Trains a small autoencoder (torch) and reports reconstruction-error statistics plus a mean+3sd anomaly threshold.', 'category': 'Machine Learning', 'icon': 'brain', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}, 'dependencies': ['numpy>=1.24', 'torch>=2.4,<3'], 'dependency_imports': ['torch']}

    def run(self, ctx, inputs):
        hidden = int(ctx.step_params.get("hidden", 12))
        epochs = int(ctx.step_params.get("epochs", 200))
        learning_rate = float(ctx.step_params.get("learning_rate", 0.05))
        seed = int(ctx.step_params.get("seed", 7))
        bottleneck = int(ctx.step_params.get("bottleneck", 1))
        data = matrix(inputs[0])
        if data.shape[1] < 2:
            raise StepError("autoencoder_anomaly needs at least two feature columns")
        try:
            import torch
            from torch import nn
        except ImportError as error:
            raise StepError("torch is required for autoencoder_anomaly") from error
        torch.manual_seed(seed)
        torch.set_num_threads(1)
        xt = torch.tensor(data, dtype=torch.float32)
        net = nn.Sequential(
            nn.Linear(data.shape[1], hidden), nn.ReLU(),
            nn.Linear(hidden, bottleneck),
            nn.Linear(bottleneck, data.shape[1]),
        )
        opt = torch.optim.Adam(net.parameters(), lr=learning_rate)
        loss_fn = nn.MSELoss()
        for _ in range(epochs):
            opt.zero_grad()
            loss = loss_fn(net(xt), xt)
            loss.backward()
            opt.step()
        with torch.no_grad():
            err = ((net(xt) - xt) ** 2).mean(dim=1).numpy()
        threshold = float(err.mean() + 3.0 * err.std())
        out = table([[float(err.mean()), float(err.max()), threshold, float((err > threshold).sum()), float(data.shape[1])]],
                    ["mse_mean", "mse_max", "threshold", "n_anomalies", "n_features"])
        ctx[ctx.step_params["output"]] = out

