"""Phospho-site localization probability from delta scores"""
import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b62b_common import column, string_column, table

class PtmLocalizationScoreStep(Step):
    parameters_file = "ptm_localization_score.PtmLocalizationScoreStep.parameters.json"

    definition = {
        "id": "ptm_localization_score",
        "version": "1.0.0",
        "title": "Phospho-site localization probability from delta scores",
        "description": "Phospho-site localization probability from delta scores",
        "category": "Proteomics",
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

        psm = string_column(inputs[0], "psm")
        delta = column(inputs[0], "delta_score")
        n = column(inputs[0], "n_candidates")
        rows = []
        vals = []
        for i, p in enumerate(psm):
            prob = 1.0 / (1.0 + 10.0 ** (-delta[i] / 10.0))
            rows.append(p)
            vals.append([prob, 1.0 if prob >= 0.75 else 0.0, n[i]])
        ctx[ctx.step_params["output"]] = table(rows, ["localization_probability", "confidence", "n_sites"], vals)
        return None
