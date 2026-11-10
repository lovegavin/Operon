"""Auto-generated b87 operator: Variational autoencoder anomaly score."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._b87_common import matrix, labels, table


class VaeAnomalyStep(Step):
    parameters_file = "vae_anomaly.VaeAnomalyStep.parameters.json"
    definition = {'id': 'vae_anomaly', 'kind': 'operator', 'version': '1.0.0', 'title': 'Variational autoencoder anomaly score', 'description': 'Variational autoencoder anomaly score (batch b87).', 'category': 'Machine Learning', 'icon': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}, 'dependencies': ['numpy>=1.24', 'torch>=2.4,<3']}

    def run(self, ctx, inputs):
        import torch
        from torch import nn
        params = ctx.step_params
        out_name = params["output"]
        x = matrix(inputs[0])
        n, d = x.shape
        hidden = int(params.get("hidden", 8))
        latent = int(params.get("latent", 2))
        epochs = int(params.get("epochs", 300))
        lr = float(params.get("learning_rate", 0.01))
        seed = int(params.get("seed", 7))
        torch.manual_seed(seed)
        np.random.seed(seed)

        class VAE(nn.Module):
            def __init__(self):
                super().__init__()
                self.e1 = nn.Linear(d, hidden)
                self.e2 = nn.Linear(hidden, hidden)
                self.mu = nn.Linear(hidden, latent)
                self.lv = nn.Linear(hidden, latent)
                self.d1 = nn.Linear(latent, hidden)
                self.d2 = nn.Linear(hidden, hidden)
                self.out = nn.Linear(hidden, d)

            def encode(self, z):
                h = torch.relu(self.e1(z))
                h = torch.relu(self.e2(h))
                return self.mu(h), self.lv(h)

            def forward(self, z):
                mu, lv = self.encode(z)
                eps = torch.randn_like(mu)
                h = torch.relu(self.d1(mu + torch.exp(0.5 * lv) * eps))
                h = torch.relu(self.d2(h))
                return self.out(h), mu, lv

        model = VAE()
        opt = torch.optim.Adam(model.parameters(), lr=lr)
        data = torch.tensor(x, dtype=torch.float32)
        model.train()
        for _ in range(max(1, epochs)):
            opt.zero_grad()
            rec, mu, lv = model(data)
            mse = ((rec - data) ** 2).mean()
            kl = (-0.5 * (1 + lv - mu ** 2 - torch.exp(lv))).mean()
            loss = mse + 1e-3 * kl
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            rec, mu, lv = model(data)
            rec_err = ((rec - data) ** 2).mean(dim=1).numpy()
            kl_vec = (-0.5 * (1 + lv - mu ** 2 - torch.exp(lv))).sum(dim=1).numpy()
        score = rec_err + 1e-3 * kl_vec
        med = float(np.median(score)); mad = float(np.median(np.abs(score - med)))
        threshold = med + 3.0 * 1.4826 * mad
        anom = (score > threshold).astype(float)
        rows = [k for k, _ in sorted(labels(inputs[0], inputs[0].dims[0]).items(), key=lambda kv: kv[1])]
        if not rows:
            rows = [f"sample_{i + 1}" for i in range(n)]
        names = rows + ["summary"]
        cols = {
            "recon_error": list(rec_err) + [float("nan")],
            "kl": list(kl_vec) + [float("nan")],
            "score": list(score) + [float("nan")],
            "is_anomaly": list(anom) + [float("nan")],
            "threshold": [float("nan")] * n + [threshold],
            "n_anomalies": [float("nan")] * n + [float(anom.sum())],
        }
        ctx[out_name] = table(names, cols)

