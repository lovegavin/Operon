"""Align retention times between two chromatographic runs"""
import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b75b_common import numeric, result_form, row_names


class RtAlignmentStep(Step):
    parameters_file = "rt_alignment.RtAlignmentStep.parameters.json"

    definition = {
        "id": "rt_alignment",
        "version": "1.0.0",
        "title": "Align retention times between runs",
        "description": "Align retention times between runs",
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
        "inputs": [{
            "version": 1,
            "numeric": True,
            "dims": [
                {"param": "row_dim", "default": "feature"},
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
    parameters_file = "rt_alignment.RtAlignmentStep.parameters.json"

    def run(self, ctx, inputs):
        names = row_names(inputs[0], "feature")
        a = numeric(inputs[0], "feature", "run_a")
        b = numeric(inputs[0], "feature", "run_b")
        delta = b - a
        shift = float(np.nanmedian(delta))
        aligned = b - shift
        data = np.column_stack([a, b, aligned, delta])
        ctx[ctx.step_params["output"]] = result_form(
            names, ["rt_a", "rt_b", "rt_aligned", "delta"], data,
            {"median_shift": float(np.round(shift, 8))})
        return None

