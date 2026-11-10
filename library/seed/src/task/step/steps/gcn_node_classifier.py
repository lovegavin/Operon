
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b89_common import matrix, named_column, table

class GcnNodeClassifierStep(Step):
    parameters_file = "gcn_node_classifier.GcnNodeClassifierStep.parameters.json"

    definition = {'id': 'gcn_node_classifier', 'version': '1.0.0', 'title': 'GCN node classifier', 'description': 'Two-layer graph convolutional network for semi-supervised node classification on a synthetic homophilous graph.', 'category': 'Machine Learning', 'kind': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 2, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}, {'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}, {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    def run(self, ctx, inputs):
        import numpy as np
        import torch
        import torch.nn as nn

        params = ctx.step_params
        X = matrix(inputs[0])
        edge = np.asarray(inputs[1].data, dtype=int)
        y = named_column(inputs[0], params["label_column"]).astype(int)
        feat = X[:, :-1]
        n, f = feat.shape
        a = torch.zeros(n, n)
        for u, v in edge:
            a[int(u), int(v)] = 1.0
            a[int(v), int(u)] = 1.0
        a = a + torch.eye(n)
        d = a.sum(dim=1).sqrt()
        ahat = a / d.unsqueeze(1) / d.unsqueeze(0)
        x = torch.tensor(feat, dtype=torch.float32)
        labels = torch.tensor(y, dtype=torch.long)

        class GCN(nn.Module):
            def __init__(self):
                super().__init__()
                self.w1 = nn.Linear(f, params["hidden"])
                self.w2 = nn.Linear(params["hidden"], int(y.max()) + 1)

            def forward(self, x):
                h = torch.relu(ahat @ self.w1(x))
                return ahat @ self.w2(h)

        torch.manual_seed(int(params["seed"]))
        model = GCN()
        opt = torch.optim.Adam(model.parameters(), lr=float(params["learning_rate"]))
        loss_fn = nn.CrossEntropyLoss()
        for _ in range(int(params["epochs"])):
            opt.zero_grad()
            logits = model(x)
            loss = loss_fn(logits, labels)
            loss.backward()
            opt.step()
        with torch.no_grad():
            logits = model(x)
            pred = logits.argmax(dim=1)
            acc = float((pred == labels).float().mean())
            ce = float(loss_fn(logits, labels))
        n_params = sum(p.numel() for p in model.parameters())
        out = table({"accuracy": [acc], "log_loss": [ce], "n_nodes": [n], "n_edges": [len(edge)],
                     "n_classes": [int(y.max()) + 1], "n_params": [n_params]},
                    ["accuracy", "log_loss", "n_nodes", "n_edges", "n_classes", "n_params"])

        ctx[params["output"]] = out
