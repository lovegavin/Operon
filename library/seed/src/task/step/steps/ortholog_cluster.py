"""Operon operator ortholog_cluster."""
import numpy as np
from src.core import Form
from src.task.step.base import Step
from ._b71_common import matrix, row_names, result_form


class OrthologClusterStep(Step):
    definition = {
    "protocol_version": 3,
    "id": "ortholog_cluster",
    "version": "1.0.0",
    "kind": "operator",
    "protocol_revision": "3.7",
    "title": "Ortholog clustering by presence-pattern similarity",
    "category": "Comparative genomics",
    "description": "Clusters genes into ortholog groups by Jaccard similarity of their presence patterns.",
    "contracts": {
        "version": 1,
        "inputs": [
            {
                "version": "1.0.0",
                "dims": [
                    {
                        "param": "genome_dim",
                        "default": "genome"
                    },
                    {
                        "param": "gene_dim",
                        "default": "gene"
                    }
                ],
                "labels": [],
                "parallel": [],
                "ndim": 2
            }
        ],
        "output": {
            "mode": "declare",
            "schema": {
                "ndim": 2,
                "numeric": True
            }
        }
    },
    "data_formats": {
        "inputs": [
            {
                "logical_type": "form",
                "representations": [
                    "form"
                ]
            }
        ],
        "outputs": [
            {
                "logical_type": "form",
                "representations": [
                    "form"
                ]
            }
        ]
    },
    "resources": {
        "memory_modes": [
            "full"
        ],
        "supports_cuda": False,
        "estimate": "estimate_memory"
    },
    "inputs_arity": 1,
    "outputs": [],
    "output_parameter": "output"
}

    parameters_file = "ortholog_cluster.OrthologClusterStep.parameters.json"

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]

        m = matrix(form) > 0
        n = m.shape[0]
        thr = float(params.get("min_jaccard", 0.8))
        parent = list(range(n))
        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra
        for i in range(n):
            for j in range(i + 1, n):
                inter = float(np.logical_and(m[i], m[j]).sum())
                union_sz = float(np.logical_or(m[i], m[j]).sum())
                if union_sz and inter / union_sz >= thr:
                    union(i, j)
        groups = {}
        for i in range(n):
            groups.setdefault(find(i), []).append(i)
        ordered = sorted(groups.values(), key=lambda g: (-len(g), g[0]))
        names = [row_names(form)[g[0]] for g in ordered]
        rows = [[float(len(g)), float(len(g)) / n] for g in ordered]
        ctx[params["output"]] = result_form(names, rows, ["cluster_size", "fraction"])
        return None

