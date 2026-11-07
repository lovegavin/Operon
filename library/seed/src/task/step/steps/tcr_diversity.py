"""Operon operator tcr_diversity."""
import numpy as np
from src.core import Form
from src.task.step.base import Step
from ._b69_common import column_index, numeric_column, string_column, result_form


class TcrDiversityStep(Step):
    definition = {
    "protocol_version": 3,
    "id": "tcr_diversity",
    "version": "1.0.0",
    "kind": "operator",
    "protocol_revision": "3.7",
    "title": "TCR repertoire diversity indices",
    "category": "Immunology",
    "description": "Computes observed richness, Shannon, Simpson, Chao1 and Pielou evenness from clonotype counts.",
    "contracts": {
        "version": 1,
        "inputs": [
            {
                "version": "1.0.0",
                "dims": [
                    {
                        "param": "sequence_dim",
                        "default": "sequence"
                    },
                    {
                        "param": "field_dim",
                        "default": "field"
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
                "numeric": True,
                "info_open": True
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

    parameters_file = "tcr_diversity.TcrDiversityStep.parameters.json"

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]

        counts = numeric_column(form, "field", str(params.get("count_column", "count")))
        counts = counts[counts > 0]
        n = float(counts.sum())
        s = float(len(counts))
        p = counts / n if n else counts
        shannon = float(-(p * np.log(p)).sum()) if n else 0.0
        simpson = float(1.0 - (p ** 2).sum()) if n else 0.0
        f1 = float((counts == 1).sum())
        f2 = float((counts == 2).sum())
        chao1 = s + (f1 * (f1 - 1.0)) / (2.0 * (f2 + 1.0)) if s else 0.0
        pielou = shannon / np.log(s) if s > 1 else 0.0
        rows = [[s, shannon, simpson, chao1, float(pielou), n]]
        ctx[params["output"]] = result_form(["repertoire"], rows,
            ["observed_clonotypes", "shannon", "simpson", "chao1", "pielou_evenness", "total_counts"])
        return None

