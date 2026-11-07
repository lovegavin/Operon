"""Protein inference"""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._ms66_common import numeric_column, result_form, string_column


class ProteinInferenceStep(Step):
    definition = {
    "protocol_version": 3,
    "protocol_revision": "3.7",
    "id": "protein_inference",
    "version": "1.0.0",
    "kind": "operator",
    "title": "Protein inference",
    "category": "Proteomics MS",
    "description": "Peptide evidence summarised to proteins with unique-peptide counts.",
    "inputs_arity": 1,
    "outputs": [],
    "output_parameter": "output",
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
    "contracts": {
        "version": 1,
        "inputs": [
            {
                "dims": [
                    {
                        "param": "peptide_dim",
                        "default": "peptide"
                    },
                    {
                        "param": "field_dim",
                        "default": "field"
                    }
                ]
            }
        ],
        "output": {
            "mode": "declare",
            "schema": {
                "ndim": 2,
                "numeric": True,
                "info_open": True
            }
        }
    },
    "resources": {
        "memory_modes": [
            "full"
        ],
        "supports_cuda": False,
        "estimate": "estimate_memory"
    }
}
    parameters_file = "protein_inference.ProteinInferenceStep.parameters.json"

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        pep = numeric_column(form, "field", "peptide_id").astype(int)
        prot = numeric_column(form, "field", "protein_id").astype(int)
        names = sorted(set(int(v) for v in prot))
        pep_sets = {name: set(int(p) for p in pep[prot == name]) for name in names}
        counts = {}
        for name in names:
            for p in pep_sets[name]:
                counts[p] = counts.get(p, 0) + 1
        rows = []
        for name in names:
            own = pep_sets[name]
            unique = sum(1 for p in own if counts[p] == 1)
            rows.append([float(len(own)), float(unique), float(len(own) - unique)])
        columns = ["n_peptides", "n_unique", "n_shared"]
        ctx[params["output"]] = result_form(names, rows, columns)

        return None
