
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._lfq_common import labels, matrix


class LfqMedianNormalizeStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "lfq_median_normalize",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Median-normalize an LFQ matrix",
        "category": "Proteomics",
        "description": "Divide each sample column by its median and rescale to the global median of medians.",
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
    parameters_file = "lfq_median_normalize.LfqMedianNormalizeStep.parameters.json"

    def run(self, ctx, inputs):
        out_name = str(ctx.step_params.get("output") or "output")
        data = matrix(inputs[0])
        mask = np.isfinite(data) & (data > 0)
        medians = np.array([np.median(data[mask[:, j], j]) if mask[:, j].any() else np.nan
                            for j in range(data.shape[1])], dtype=float)
        finite = medians[np.isfinite(medians)]
        if finite.size == 0:
            raise ValueError("no finite positive intensities")
        target = float(np.median(finite))
        factors = np.where(np.isfinite(medians), medians / target, 1.0)
        out_data = data / factors[None, :]
        out_data[~np.isfinite(data)] = np.nan
        out = Form(data=out_data, dims=list(inputs[0].dims), labels=labels(inputs[0]),
                   info={"matrix_kind": "lfq_normalized", "method": "median",
                         "target_median": target,
                         "factors": {str(i): float(f) for i, f in enumerate(factors)}})
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
