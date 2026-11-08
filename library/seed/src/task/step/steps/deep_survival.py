"""Auto-generated b87 operator: DeepSurv Cox proportional hazards network."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._b87_common import matrix, labels, table


class DeepSurvivalStep(Step):
    parameters_file = "deep_survival.DeepSurvivalStep.parameters.json"
    definition = {'id': 'deep_survival', 'kind': 'operator', 'version': '1.0.0', 'title': 'DeepSurv Cox proportional hazards network', 'description': 'DeepSurv Cox proportional hazards network (batch b87).', 'category': 'Machine Learning', 'icon': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}, 'dependencies': ['numpy>=1.24', 'torch>=2.4,<3']}

    def run(self, ctx, inputs):
        import torch
        from torch import nn
        params = ctx.step_params
        out_name = params["output"]
        tab = matrix(inputs[0])
        tcol = params.get("time_column", "time")
        ecol = params.get("event_column", "event")
        hidden = int(params.get("hidden", 16))
        epochs = int(params.get("epochs", 300))
        lr = float(params.get("learning_rate", 0.01))
        seed = int(params.get("seed", 7))
        lab = labels(inputs[0], inputs[0].dims[1])
        if tcol not in lab or ecol not in lab:
            raise ValueError(f"missing time/event columns: {tcol}/{ecol}")
        t = tab[:, lab[tcol]]
        e = tab[:, lab[ecol]]
        feat_idx = [lab[k] for k, _ in sorted(lab.items(), key=lambda kv: kv[1]) if k not in (tcol, ecol)]
        x = tab[:, feat_idx]
        mu = x.mean(0); sd = x.std(0); sd[sd == 0] = 1.0
        x = (x - mu) / sd
        torch.manual_seed(seed)
        d = x.shape[1]

        class Net(nn.Module):
            def __init__(self):
                super().__init__()
                self.a = nn.Linear(d, hidden)
                self.b = nn.Linear(hidden, 1)

            def forward(self, z):
                return self.b(torch.relu(self.a(z))).squeeze(1)

        model = Net()
        opt = torch.optim.Adam(model.parameters(), lr=lr)
        xt = torch.tensor(x, dtype=torch.float32)
        tt = torch.tensor(t, dtype=torch.float32)
        et = torch.tensor(e, dtype=torch.float32)
        model.train()
        for _ in range(max(1, epochs)):
            opt.zero_grad()
            risk = model(xt)
            order = torch.argsort(tt, descending=True)
            r = risk[order]; ev = et[order]
            logcum = torch.logcumsumexp(r, dim=0)
            ll = (r - logcum) * ev
            loss = -ll.sum() / torch.clamp(ev.sum(), min=1.0)
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            risk = model(xt).numpy()
        order = np.argsort(-t)
        r = risk[order]; ev = e[order]
        logcum = np.logaddexp.accumulate(r)
        ll = float(np.sum((r - logcum) * ev))
        conc = 0.0; pairs = 0
        for i in range(len(t)):
            for j in range(i + 1, len(t)):
                if e[i] == 1 and t[i] < t[j]:
                    pairs += 1; conc += 1.0 if risk[i] > risk[j] else (0.5 if risk[i] == risk[j] else 0.0)
                elif e[j] == 1 and t[j] < t[i]:
                    pairs += 1; conc += 1.0 if risk[j] > risk[i] else (0.5 if risk[j] == risk[i] else 0.0)
        cidx = conc / pairs if pairs else 0.5
        n_params = sum(p.numel() for p in model.parameters())
        ctx[out_name] = table(["model"], {
            "c_index": [cidx], "log_likelihood": [ll], "n_samples": [float(len(t))],
            "n_events": [float(e.sum())], "n_features": [float(d)], "n_params": [float(n_params)],
        })

