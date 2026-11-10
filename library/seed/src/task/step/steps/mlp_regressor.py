"""Train a small MLP regressor

Fits a two-layer perceptron (torch) on a feature table with a target column and reports RMSE, MAE and R2.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step
from src.task.step.steps._b85_common import matrix, named_column, table

class MlpRegressorStep(Step):
    parameters_file = "mlp_regressor.MlpRegressorStep.parameters.json"
    definition = {'protocol_version': 3, 'protocol_revision': '3.7', 'kind': 'operator', 'id': 'mlp_regressor', 'version': '1.0.0', 'title': 'Train a small MLP regressor', 'description': 'Fits a two-layer perceptron (torch) on a feature table with a target column and reports RMSE, MAE and R2.', 'category': 'Machine Learning', 'icon': 'brain', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}, 'dependencies': ['numpy>=1.24', 'torch>=2.4,<3'], 'dependency_imports': ['torch']}

    def run(self, ctx, inputs):
        hidden = int(ctx.step_params.get("hidden", 12))
        epochs = int(ctx.step_params.get("epochs", 200))
        learning_rate = float(ctx.step_params.get("learning_rate", 0.05))
        seed = int(ctx.step_params.get("seed", 7))
        data = matrix(inputs[0])
        target = named_column(inputs[0], "target")
        target_idx = int(inputs[0].labels[inputs[0].dims[1]]["target"])
        x = np.delete(data, target_idx, axis=1)
        y = target.astype(float)
        try:
            import torch
            from torch import nn
        except ImportError as error:
            raise StepError("torch is required for mlp_regressor") from error
        torch.manual_seed(seed)
        torch.set_num_threads(1)
        xt = torch.tensor(x, dtype=torch.float32)
        yt = torch.tensor(y, dtype=torch.float32).reshape(-1, 1)
        net = nn.Sequential(nn.Linear(x.shape[1], hidden), nn.ReLU(), nn.Linear(hidden, 1))
        opt = torch.optim.Adam(net.parameters(), lr=learning_rate)
        loss_fn = nn.MSELoss()
        for _ in range(epochs):
            opt.zero_grad()
            loss = loss_fn(net(xt), yt)
            loss.backward()
            opt.step()
        with torch.no_grad():
            pred = net(xt).numpy().reshape(-1)
        rmse = float(np.sqrt(np.mean((pred - y) ** 2)))
        mae = float(np.mean(np.abs(pred - y)))
        sst = float(np.sum((y - y.mean()) ** 2))
        r2 = 0.0 if sst == 0 else float(1.0 - np.sum((pred - y) ** 2) / sst)
        n_params = int(sum(p.numel() for p in net.parameters()))
        out = table([[rmse, mae, r2, float(len(y)), float(n_params)]],
                    ["rmse", "mae", "r2", "n_train", "n_params"])
        ctx[ctx.step_params["output"]] = out

