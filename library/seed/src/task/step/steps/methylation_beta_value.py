from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step
from src.task.step.steps._meth_common import decode_column, numeric_column, probe_form


class MethylationBetaValueStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "methylation_beta_value",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Methylation beta values",
        "category": "Epigenomics",
        "description": "Compute per-probe beta values for two groups from methylated and unmethylated counts.",
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
    parameters_file = "methylation_beta_value.MethylationBetaValueStep.parameters.json"

    def run(self, ctx, inputs):
        p = ctx.step_params
        out_name = str(p.get("output") or "output")
        probe_dim = str(p.get("probe_dim") or "probe")
        field_dim = str(p.get("field_dim") or "field")
        m1 = numeric_column(inputs[0], field_dim, "group1_methylated")
        u1 = numeric_column(inputs[0], field_dim, "group1_unmethylated")
        m2 = numeric_column(inputs[0], field_dim, "group2_methylated")
        u2 = numeric_column(inputs[0], field_dim, "group2_unmethylated")
        if np.any(m1 < 0) or np.any(u1 < 0) or np.any(m2 < 0) or np.any(u2 < 0):
            raise StepError("methylation_beta_value: counts must be non-negative")
        cov1 = m1 + u1
        cov2 = m2 + u2
        min_cov = float(p.get("min_coverage", 10))
        beta1 = np.where(cov1 >= min_cov, m1 / np.maximum(cov1, 1.0), np.nan)
        beta2 = np.where(cov2 >= min_cov, m2 / np.maximum(cov2, 1.0), np.nan)
        delta = beta1 - beta2
        labels = {str(i): i for i in range(len(m1))}
        ctx[out_name] = probe_form(["beta1", "beta2", "delta", "coverage1", "coverage2"], [beta1, beta2, delta, cov1, cov2], labels)
