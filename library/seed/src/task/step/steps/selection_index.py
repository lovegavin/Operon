"""Composite selection score from Fst, iHS and XP-EHH"""
import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b75b_common import numeric, result_form, row_names


class SelectionIndexStep(Step):
    parameters_file = "selection_index.SelectionIndexStep.parameters.json"

    definition = {
        "id": "selection_index",
        "version": "1.0.0",
        "title": "Composite selection score from Fst, iHS and XP-EHH",
        "description": "Composite selection score from Fst, iHS and XP-EHH",
        "category": "Population genetics",
        "icon": "Table",
    "protocol_version": 3,
    "protocol_revision": "3.7",
    "kind": "operator",
    "inputs_arity": 1,
    "output_parameter": "output",
    "outputs": [],
    "contracts": {
        "version": 1,
        "inputs": [{
            "version": 1,
            "numeric": True,
            "dims": [
                {"param": "row_dim", "default": "variant"},
                {"param": "field_dim", "default": "field"}
            ],
            "labels": [],
            "parallel": [],
            "ndim": 2
        }],
        "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    },
    "data_formats": {
        "inputs": [{"logical_type": "form", "representations": ["form"]}],
        "outputs": [{"logical_type": "form", "representations": ["form"]}]
    },
    "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"}
    }
    parameters_file = "selection_index.SelectionIndexStep.parameters.json"

    def run(self, ctx, inputs):
        names = row_names(inputs[0], "variant")
        cols, labels = [], []
        for name in ["fst", "ihs", "xpehh"]:
            v = numeric(inputs[0], "variant", name)
            sd = float(np.nanstd(v, ddof=1)) if len(v) > 1 else 0.0
            z = (v - float(np.nanmean(v))) / sd if sd > 0 else np.zeros_like(v)
            cols.append(z)
            labels.append(name + "_z")
        z = np.column_stack(cols)
        score = np.nanmean(np.abs(z), axis=1)
        order = np.argsort(-score)
        rank = np.empty(len(order))
        rank[order] = np.arange(1, len(order) + 1)
        data = np.column_stack([z, score, rank])
        ctx[ctx.step_params["output"]] = result_form(names, labels + ["composite", "rank"], data)
        return None

