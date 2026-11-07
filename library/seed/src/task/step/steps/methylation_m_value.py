from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step
from src.task.step.steps._meth_common import decode_column, numeric_column, probe_form


class MethylationMValueStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "methylation_m_value",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Methylation M values",
        "category": "Epigenomics",
        "description": "Compute log2 methylated/unmethylated M values for two groups.",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "numeric": False,
                    "dims": [
                        {"param": "probe_dim", "default": "probe"},
                        {"param": "field_dim", "default": "field"},
                    ],
                    "labels": [],
                    "parallel": [],
                }
            ],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
    }
    parameters_file = "methylation_m_value.MethylationMValueStep.parameters.json"

    def run(self, ctx, inputs):
        p = ctx.step_params
        out_name = str(p.get("output") or "output")
        probe_dim = str(p.get("probe_dim") or "probe")
        field_dim = str(p.get("field_dim") or "field")
        m1 = numeric_column(inputs[0], field_dim, "group1_methylated")
        u1 = numeric_column(inputs[0], field_dim, "group1_unmethylated")
        m2 = numeric_column(inputs[0], field_dim, "group2_methylated")
        u2 = numeric_column(inputs[0], field_dim, "group2_unmethylated")
        mv1 = np.log2((m1 + 1.0) / (u1 + 1.0))
        mv2 = np.log2((m2 + 1.0) / (u2 + 1.0))
        ctx[out_name] = probe_form(["m1", "m2", "delta_m"], [mv1, mv2, mv1 - mv2], {str(i): i for i in range(len(m1))})
