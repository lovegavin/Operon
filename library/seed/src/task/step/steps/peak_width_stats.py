"""Width distribution of narrowPeak intervals."""

from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._peak_common import metric_form, numeric_column

_NAMES = [
    "n_peaks",
    "mean_width",
    "median_width",
    "sd_width",
    "min_width",
    "max_width",
    "p90_width",
    "total_bp",
]


class PeakWidthStatsStep(Step):
    provider = "operon-core"
    parameters_file = "peak_width_stats.PeakWidthStatsStep.parameters.json"

    definition = {
        "protocol_revision": "3.7",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
        "protocol_version": 3,
        "id": "peak_width_stats",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Peak width distribution",
        "description": "Summarize narrowPeak interval widths in base pairs.",
        "category": "Epigenomics",
        "icon": "ChartBar",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "region_dim", "default": "region"},
                        {"param": "field_dim", "default": "field"},
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                    "info": {"missing_code": {"type": ["number", "null"]}},
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True,
                    "info": {"missing_code": {"type": ["number", "null"]}},
                },
            },
        },
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        total = sum(int(np.asarray(getattr(i, "data", [])).nbytes) for i in inputs)
        return (max(total, 8 * 1024 * 1024), 1024 * 1024)

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        out_name = params.get("output", self.name)
        field_dim = str(params.get("field_dim", "field"))
        form = inputs[0]
        starts = numeric_column(form, field_dim, "start", "peak_width_stats")
        ends = numeric_column(form, field_dim, "end", "peak_width_stats")
        widths = ends - starts
        if np.any(widths < 0):
            raise StepError("peak_width_stats: end must be >= start")
        if widths.size == 0:
            raise StepError("peak_width_stats: no peaks in input")
        values = [
            float(widths.size),
            float(np.mean(widths)),
            float(np.median(widths)),
            float(np.std(widths, ddof=1)) if widths.size > 1 else 0.0,
            float(np.min(widths)),
            float(np.max(widths)),
            float(np.percentile(widths, 90)),
            float(np.sum(widths)),
        ]
        ctx[out_name] = metric_form(_NAMES, values, {"unit": "bp", "n_peaks": int(widths.size)})
        self._export_data = {
            "output": out_name,
            "n_peaks": int(widths.size),
            "mean_width": float(np.mean(widths)),
            "median_width": float(np.median(widths)),
        }
