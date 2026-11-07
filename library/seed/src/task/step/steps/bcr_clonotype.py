"""Operon operator bcr_clonotype."""
import numpy as np
from src.core import Form
from src.task.step.base import Step
from ._b69_common import column_index, numeric_column, string_column, result_form


class BcrClonotypeStep(Step):
    definition = {
    "protocol_version": 3,
    "id": "bcr_clonotype",
    "version": "1.0.0",
    "kind": "operator",
    "protocol_revision": "3.7",
    "title": "BCR clonotype grouping and expansion",
    "category": "Immunology",
    "description": "Groups BCR sequences by V gene and CDR3 amino-acid sequence and reports clone sizes.",
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

    parameters_file = "bcr_clonotype.BcrClonotypeStep.parameters.json"

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]

        cdr3 = string_column(form, "field", str(params.get("cdr3_column", "cdr3_aa")))
        vgene = string_column(form, "field", str(params.get("v_gene_column", "v_gene")))
        counts = numeric_column(form, "field", str(params.get("count_column", "count")))
        groups = {}
        for c, v, n in zip(cdr3, vgene, counts):
            groups[(v, c)] = groups.get((v, c), 0.0) + float(n)
        total = sum(groups.values()) or 1.0
        ordered = sorted(groups.items(), key=lambda kv: (-kv[1], kv[0][1]))
        rows = [[size, size / total, float(rank + 1)] for rank, (_, size) in enumerate(ordered)]
        names = [f"{v}|{c}" for (v, c), _ in ordered]
        columns = ["clone_size", "frequency", "rank"]
        info = {"n_clones": len(ordered), "n_sequences": int(len(cdr3)), "n_expanded": int(sum(1 for _, s in ordered if s >= 2))}
        out = result_form(names, rows, columns)
        out.info.update(info)
        ctx[params["output"]] = out
        return None

