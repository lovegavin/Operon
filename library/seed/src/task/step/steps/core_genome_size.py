"""Operon operator core_genome_size."""
import numpy as np
from src.core import Form
from src.task.step.base import Step
from ._b71_common import matrix, row_names, result_form


class CoreGenomeSizeStep(Step):
    definition = {
    "protocol_version": 3,
    "id": "core_genome_size",
    "version": "1.0.0",
    "kind": "operator",
    "protocol_revision": "3.7",
    "title": "Core genome size and fractions",
    "category": "Comparative genomics",
    "description": "Summarises core and accessory gene counts from a presence/absence matrix.",
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

    parameters_file = "core_genome_size.CoreGenomeSizeStep.parameters.json"

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]

        m = matrix(form) > 0
        names = row_names(form)
        n_genes = m.shape[1]
        per_gene = m.sum(axis=0)
        core = per_gene == m.shape[0]
        rows = []
        for i in range(m.shape[0]):
            present = float(m[i].sum())
            rows.append([present, float(core.sum()), present - float(core.sum()),
                         float(core.sum()) / present if present else 0.0])
        ctx[params["output"]] = result_form(names, rows,
            ["genes_present", "core_genes", "accessory_genes", "core_fraction"])
        return None

