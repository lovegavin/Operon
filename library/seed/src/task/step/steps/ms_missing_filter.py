
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._lfq_common import labels, matrix


class MsMissingFilterStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "ms_missing_filter",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Filter proteins by missing-value fraction",
        "category": "Proteomics",
        "description": "Remove proteins whose missing fraction exceeds a threshold and report counts.",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "numeric": True,
                    "dims": [
                        {"param": "protein_dim", "default": "protein"},
                        {"param": "sample_dim", "default": "sample"},
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
    parameters_file = "ms_missing_filter.MsMissingFilterStep.parameters.json"

    def run(self, ctx, inputs):
        out_name = str(ctx.step_params.get("output") or "output")
        data = matrix(inputs[0])
        missing = ~np.isfinite(data) | (data <= 0)
        frac = missing.mean(axis=1) if data.size else np.zeros(0)
        keep = frac <= float(ctx.step_params.get("max_missing_fraction", 0.5)) + 1e-12
        out_data = data[keep]
        p_dim, s_dim = inputs[0].dims
        protein_labels = inputs[0].labels.get(p_dim, {})
        ordered = sorted(protein_labels.items(), key=lambda kv: kv[1])
        kept = {str(name): i for i, (name, idx) in enumerate(
            (n, idx) for n, idx in ordered if keep[idx])}
        out = Form(data=out_data, dims=[p_dim, s_dim],
                   labels={p_dim: kept, s_dim: dict(inputs[0].labels.get(s_dim, {}))},
                   info={"matrix_kind": "lfq_filtered",
                         "n_input": int(data.shape[0]), "n_kept": int(keep.sum()),
                         "n_removed": int((~keep).sum()),
                         "max_missing_fraction": float(ctx.step_params.get("max_missing_fraction", 0.5))})
        out.validate()
        ctx[out_name] = out
        return None

    def export(self, ctx):
        out = ctx[str(ctx.step_params.get("output") or "output")]
        return {
            "result_files": [],
            "values": {
                str(ctx.step_params.get("output") or "output"): {
                    "dims": list(out.dims),
                    "rows": int(out.data.shape[0]),
                    "columns": int(out.data.shape[1]),
                }
            },
        }
