
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._lfq_common import labels, matrix


class LfqQuantileNormalizeStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "lfq_quantile_normalize",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Quantile-normalize an LFQ matrix",
        "category": "Proteomics",
        "description": "Rank-align every sample column to the mean empirical quantile distribution.",
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
    parameters_file = "lfq_quantile_normalize.LfqQuantileNormalizeStep.parameters.json"

    def run(self, ctx, inputs):
        out_name = str(ctx.step_params.get("output") or "output")
        data = matrix(inputs[0])
        mask = np.isfinite(data) & (data > 0)
        n_rows, n_cols = data.shape
        ranks = np.full(data.shape, -1, dtype=int)
        sorted_cols = []
        for j in range(n_cols):
            idx = np.flatnonzero(mask[:, j])
            order = idx[np.argsort(data[idx, j], kind="mergesort")]
            sorted_cols.append(data[order, j])
            ranks[order, j] = np.arange(order.size)
        lengths = [c.size for c in sorted_cols]
        max_len = max(lengths) if lengths else 0
        if max_len == 0:
            raise ValueError("no finite positive intensities")
        quantiles = np.full(max_len, np.nan)
        for r in range(max_len):
            vals = [c[min(r, c.size - 1)] for c in sorted_cols if c.size]
            quantiles[r] = float(np.mean(vals))
        out_data = data.copy()
        for j in range(n_cols):
            idx = np.flatnonzero(mask[:, j])
            order = idx[np.argsort(data[idx, j], kind="mergesort")]
            out_data[order, j] = quantiles[:order.size]
        out_data[~mask & ~np.isfinite(data)] = np.nan
        out = Form(data=out_data, dims=list(inputs[0].dims), labels=labels(inputs[0]),
                   info={"matrix_kind": "lfq_normalized", "method": "quantile",
                         "n_quantiles": int(max_len)})
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
