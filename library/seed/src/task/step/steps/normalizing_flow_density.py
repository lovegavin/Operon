
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b89_common import matrix, named_column, table

class NormalizingFlowDensityStep(Step):
    parameters_file = "normalizing_flow_density.NormalizingFlowDensityStep.parameters.json"

    definition = {'id': 'normalizing_flow_density', 'version': '1.0.0', 'title': 'RealNVP normalizing flow density', 'description': 'RealNVP affine-coupling flow trained by maximum likelihood on a 2-D table, reporting latent Gaussianity and parameters.', 'category': 'Machine Learning', 'kind': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    def run(self, ctx, inputs):
        import numpy as np
        import torch
        import torch.nn as nn

        params = ctx.step_params
        x = matrix(inputs[0])
        n, dim = x.shape
        xt = torch.tensor(x, dtype=torch.float32)

        class Flow(nn.Module):
            def __init__(self):
                super().__init__()
                h = int(params["hidden"])
                self.layers = nn.ModuleList()
                self.dims = []
                for i in range(int(params["layers"])):
                    m = i % dim
                    other = [j for j in range(dim) if j != m]
                    self.dims.append((m, other))
                    self.layers.append(nn.Sequential(nn.Linear(len(other), h), nn.Tanh(), nn.Linear(h, 2)))

            def forward(self, z):
                logdet = torch.zeros(z.shape[0])
                for (m, other), net in zip(self.dims, self.layers):
                    st = net(z[:, other])
                    s = st[:, 0].clamp(-3.0, 3.0)
                    t = st[:, 1]
                    z = z.clone()
                    z[:, m] = (z[:, m] - t) * torch.exp(-s)
                    logdet = logdet - s
                return z, logdet

        torch.manual_seed(int(params["seed"]))
        model = Flow()
        opt = torch.optim.Adam(model.parameters(), lr=float(params["learning_rate"]))
        for _ in range(int(params["epochs"])):
            opt.zero_grad()
            z, logdet = model(xt)
            logp = -0.5 * (z ** 2).sum(dim=1) - 0.5 * dim * np.log(2 * np.pi) + logdet
            loss = -logp.mean()
            loss.backward()
            opt.step()
        with torch.no_grad():
            z, logdet = model(xt)
            logp = -0.5 * (z ** 2).sum(dim=1) - 0.5 * dim * np.log(2 * np.pi) + logdet
            zc = z - z.mean(dim=0)
            corr = float((zc[:, 0] * zc[:, 1]).mean() / (zc[:, 0].std() * zc[:, 1].std() + 1e-12))
            zmean = float(z.mean().item())
            zstd = float(z.std().item())
            ll = float(logp.mean())
        n_params = sum(p.numel() for p in model.parameters())
        out = table({"log_likelihood": [ll], "n_samples": [n], "n_params": [n_params],
                     "latent_mean": [zmean], "latent_std": [zstd], "latent_corr": [corr]},
                    ["log_likelihood", "n_samples", "n_params", "latent_mean", "latent_std", "latent_corr"])

        ctx[params["output"]] = out
