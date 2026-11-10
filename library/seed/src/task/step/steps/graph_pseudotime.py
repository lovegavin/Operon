"""Graph pseudotime (b95)."""

from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._b95_common import column, columns, matrix, table


class GraphPseudotimeStep(Step):
    parameters_file = "graph_pseudotime.GraphPseudotimeStep.parameters.json"
    definition = {'id': 'graph_pseudotime', 'version': '1.0.0', 'title': 'Graph pseudotime', 'description': 'Graph-geodesic pseudotime from a PCA space and a k-nearest-neighbour graph.', 'category': 'Single cell', 'icon': 'trajectory', 'protocol_version': 3, 'protocol_revision': '3.7', 'kind': 'operator', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    def run(self, ctx, inputs):
        X = matrix(inputs[0])
        n = X.shape[0]
        k = int(ctx.step_params.get("n_components", 5))
        n_neighbors = int(ctx.step_params.get("n_neighbors", 10))
        root = int(ctx.step_params.get("root_cell", 0))
        if n < 5 or X.shape[1] < 2:
            raise ValueError("need at least 5 cells and 2 genes")
        n_neighbors = max(1, min(n_neighbors, n - 1))
        X = X - X.mean(0)
        U, S, Vt = np.linalg.svd(X, full_matrices=False)
        k = min(k, S.size)
        Z = U[:, :k] * S[:k]
        d2 = ((Z[:, None, :] - Z[None, :, :]) ** 2).sum(-1)
        idx = np.argsort(d2, axis=1)[:, 1:n_neighbors + 1]
        sigma2 = np.median(d2[np.arange(n), idx[:, -1]]) or 1.0
        W = np.zeros((n, n))
        for i in range(n):
            W[i, idx[i]] = np.exp(-d2[i, idx[i]] / (2 * sigma2))
        W = np.maximum(W, W.T)
        deg = W.sum(1)
        deg[deg == 0] = 1.0
        Ssym = W / np.sqrt(np.outer(deg, deg))
        evals, evecs = np.linalg.eigh(Ssym)
        order = np.argsort(evals)[::-1]
        evals, evecs = evals[order], evecs[:, order]
        coords = evecs[:, 1:k + 1] / np.sqrt(deg)[:, None]
        from scipy.sparse import csr_matrix
        from scipy.sparse.csgraph import dijkstra
        rows = np.repeat(np.arange(n), n_neighbors)
        cols = idx.reshape(-1)
        w = np.sqrt(d2[rows, cols]).clip(1e-9)
        graph = csr_matrix((np.concatenate([w, w]), (np.concatenate([rows, cols]), np.concatenate([cols, rows]))), shape=(n, n))
        dist = dijkstra(graph, directed=False, indices=root)
        if not np.isfinite(dist).all():
            raise ValueError("k-nearest-neighbour graph is disconnected; increase n_neighbors")
        pt = (dist - dist.min()) / (dist.max() - dist.min() + 1e-12)
        vals = {"pseudotime": pt}
        for j in range(min(2, coords.shape[1])):
            vals[f"dc{j + 1}"] = coords[:, j]
        out = table("cell", [str(i) for i in range(n)], vals)
        ctx[ctx.step_params["output"]] = out
