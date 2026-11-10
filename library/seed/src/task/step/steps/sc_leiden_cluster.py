"""Leiden community detection on a cell graph."""
from __future__ import annotations

import igraph as ig
import leidenalg
import numpy as np

from src.core import Form
from src.task.step.base import Step
from src.core.errors import StepError
from ._sc_common import matrix, row_names, result_form


class ScLeidenClusterStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "sc_leiden_cluster",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Leiden clustering",
        "category": "Single cell",
        "description": "Leiden community detection over a cell-cell graph.",
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"]}],
            "outputs": [{"logical_type": "form", "representations": ["form"]}],
        },
        "contracts": {
            "version": 1,
            "inputs": [{"dims": [{"param": "cell_dim", "default": "cell"}, {"param": "cell2_dim", "default": "cell2"}]}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
    }
    parameters_file = "sc_leiden_cluster.ScLeidenClusterStep.parameters.json"

    def run(self, ctx, inputs):
        params = ctx.step_params
        adj = matrix(inputs[0])
        if adj.ndim != 2 or adj.shape[0] != adj.shape[1]:
            raise StepError("sc_leiden_cluster requires a square cell-by-cell adjacency matrix")
        edges = [(i, j, float(adj[i, j])) for i in range(adj.shape[0]) for j in range(i + 1, adj.shape[1]) if adj[i, j] > 0]
        g = ig.Graph(n=adj.shape[0], edges=[(i, j) for i, j, _ in edges], directed=False)
        g.es["weight"] = [w for _, _, w in edges]
        part = leidenalg.find_partition(g, leidenalg.RBConfigurationVertexPartition,
                                        weights="weight", resolution_parameter=float(params.get("resolution", 1.0)),
                                        seed=int(params.get("seed", 0)))
        memb = np.asarray(part.membership, dtype=float)
        deg = adj.sum(axis=1)
        sizes = {c: float(np.sum(memb == c)) for c in set(part.membership)}
        data = np.column_stack([memb, deg, [sizes[int(c)] for c in memb]])
        ctx[params["output"]] = result_form("cell", row_names(inputs[0], inputs[0].dims[0]),
                                            ["cluster", "degree", "cluster_size"], data,
                                            info={"n_clusters": int(len(sizes)),
                                                  "modularity": float(part.modularity)})
        return None


def export(ctx):
    return ctx._export_data()
