"""Heuristic MHC-I anchor score for 9-mer peptides"""
import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b62b_common import column, string_column, table

class MhcAnchorScoreStep(Step):
    parameters_file = "mhc_anchor_score.MhcAnchorScoreStep.parameters.json"

    definition = {
        "id": "mhc_anchor_score",
        "version": "1.0.0",
        "title": "Heuristic MHC-I anchor score for 9-mer peptides",
        "description": "Heuristic MHC-I anchor score for 9-mer peptides",
        "category": "Immunology",
        "icon": "Table",
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "kind": "operator",
        "inputs_arity": 1,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "numeric": True, "dims": [{"param": "row_dim", "default": "row"}, {"param": "field_dim", "default": "field"}], "labels": [], "parallel": [], "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
        },
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"]}],
            "outputs": [{"logical_type": "form", "representations": ["form"]}]
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"}
    }

    def run(self, ctx, inputs):

        seqs = string_column(inputs[0], "sequence")
        hydro = set("LIVMFWY")
        rows = []
        vals = []
        for i, s in enumerate(seqs):
            a2 = s[1] if len(s) > 1 else "-"
            a9 = s[8] if len(s) > 8 else "-"
            s2 = 1.0 if a2 in hydro else 0.0
            s9 = 1.0 if a9 in hydro else 0.0
            rows.append("pep%d" % (i + 1))
            vals.append([s2 + s9, s2, s9, 1.0 if len(s) == 9 else 0.0])
        ctx[ctx.step_params["output"]] = table(rows, ["anchor_score", "p2_hydrophobic", "p9_hydrophobic", "length_ok"], vals)
        return None
