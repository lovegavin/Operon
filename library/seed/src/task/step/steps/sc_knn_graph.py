"""k-nearest-neighbour cell graph."""
from __future__ import annotations

import numpy as np
from sklearn.neighbors import NearestNeighbors

from src.core import Form
from src.task.step.base import Step
from ._sc_common import matrix, row_names


class ScKnnGraphStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "sc_knn_graph",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Single-cell kNN graph",
        "category": "Single cell",
        "description": "Build a symmetric kNN graph from a cell embedding.",
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"]}],
            "outputs": [{"logical_type": "form", "representations": ["form"]}],
        },
        "contracts": {
            "version": 1,
            "inputs": [{"dims": [{"param": "cell_dim", "default": "cell"}, {"param": "feature_dim", "default": "feature"}]}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
    }
    parameters_file = "sc_knn_graph.ScKnnGraphStep.parameters.json"

    def run(self, ctx, inputs):
        params = ctx.step_params
        x = matrix(inputs[0])
        k = max(1, min(int(params.get("k", 15)), x.shape[0] - 1))
        nn = NearestNeighbors(n_neighbors=k + 1, metric=params.get("metric", "euclidean")).fit(x)
        dist, idx = nn.kneighbors(x)
        n = x.shape[0]
        w = np.zeros((n, n), dtype=float)
        for i in range(n):
            for d, j in zip(dist[i, 1:], idx[i, 1:]):
                w[i, j] = np.exp(-float(d) ** 2)
        w = np.maximum(w, w.T)
        np.fill_diagonal(w, 0.0)
        names = row_names(inputs[0], inputs[0].dims[0])
        labels = {n_: i for i, n_ in enumerate(names)}
        out = Form(data=w, dims=["cell", "cell2"],
                   labels={"cell": labels, "cell2": dict(labels)},
                   info={"missing_code": np.nan, "k": k})
        out.validate()
        ctx[params["output"]] = out
        return None


def export(ctx):
    return ctx._export_data()
