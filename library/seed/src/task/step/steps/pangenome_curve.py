"""Operon operator pangenome_curve."""
import numpy as np
from src.core import Form
from src.task.step.base import Step
from ._b71_common import matrix, row_names, result_form


class PangenomeCurveStep(Step):
    definition = {
    "protocol_version": 3,
    "id": "pangenome_curve",
    "version": "1.0.0",
    "kind": "operator",
    "protocol_revision": "3.7",
    "title": "Pangenome accumulation curve",
    "category": "Comparative genomics",
    "description": "Estimates the pangenome size for each number of genomes by resampling genome orders.",
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

    parameters_file = "pangenome_curve.PangenomeCurveStep.parameters.json"

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]

        m = matrix(form) > 0
        n = m.shape[0]
        perms = int(params.get("permutations", 50))
        seed = int(params.get("seed", 7))
        rng = np.random.default_rng(seed)
        rows = []
        for k in range(1, n + 1):
            vals = []
            for _ in range(perms):
                order = rng.permutation(n)[:k]
                vals.append(float(m[order].any(axis=0).sum()))
            rows.append([float(k), float(np.mean(vals))])
        ctx[params["output"]] = result_form([f"k{i+1}" for i in range(n)], rows,
            ["genomes", "mean_pangenome_genes"])
        return None

