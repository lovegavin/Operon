"""Operon operator cdr3_properties."""
import numpy as np
from src.core import Form
from src.task.step.base import Step
from ._b69_common import column_index, numeric_column, string_column, result_form


class Cdr3PropertiesStep(Step):
    definition = {
    "protocol_version": 3,
    "id": "cdr3_properties",
    "version": "1.0.0",
    "kind": "operator",
    "protocol_revision": "3.7",
    "title": "CDR3 amino-acid composition and properties",
    "category": "Immunology",
    "description": "Reports length, charged fraction, hydrophobic fraction, cysteine count and aromatic fraction per CDR3.",
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

    parameters_file = "cdr3_properties.Cdr3PropertiesStep.parameters.json"

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]

        seqs = string_column(form, "field", str(params.get("cdr3_column", "cdr3_aa")))
        charged = set("KRHDE")
        hydrophobic = set("AVILMFWY")
        aromatic = set("FWY")
        rows = []
        for seq in seqs:
            s = seq.upper()
            length = len(s)
            rows.append([
                float(length),
                sum(a in charged for a in s) / length if length else 0.0,
                sum(a in hydrophobic for a in s) / length if length else 0.0,
                float(s.count("C")),
                sum(a in aromatic for a in s) / length if length else 0.0,
            ])
        ctx[params["output"]] = result_form(seqs, rows,
            ["length", "charged_fraction", "hydrophobic_fraction", "cysteines", "aromatic_fraction"])
        return None

