"""Position of the narrowPeak summit inside each interval."""

from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._peak_common import metric_form, numeric_column

_NAMES = [
    "n_peaks",
    "n_summit_valid",
    "mean_offset",
    "median_offset",
    "mean_center_deviation",
    "frac_centered_50",
    "mean_relative_position",
]


class PeakSummitOffsetStep(Step):
    provider = "operon-core"
    parameters_file = "peak_summit_offset.PeakSummitOffsetStep.parameters.json"

    definition = {
        "protocol_revision": "3.7",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
        "protocol_version": 3,
        "id": "peak_summit_offset",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Peak summit offset",
        "description": "Summarize the narrowPeak summit offset relative to the interval start and center.",
        "category": "Epigenomics",
        "icon": "ArrowsHorizontal",
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
        tolerance = float(params.get("center_tolerance_bp", 50))
        form = inputs[0]
        starts = numeric_column(form, field_dim, "start", "peak_summit_offset")
        ends = numeric_column(form, field_dim, "end", "peak_summit_offset")
        summits = numeric_column(form, field_dim, "peak", "peak_summit_offset")
        widths = ends - starts
        valid = (summits >= 0) & (summits < widths)
        if not np.any(valid):
            raise StepError("peak_summit_offset: no valid summit column values")
        offsets = summits[valid]
        valid_widths = widths[valid]
        center_deviation = np.abs(offsets - (valid_widths - 1.0) / 2.0)
        values = [
            float(widths.size),
            float(offsets.size),
            float(np.mean(offsets)),
            float(np.median(offsets)),
            float(np.mean(center_deviation)),
            float(np.mean(center_deviation <= tolerance)),
            float(np.mean(offsets / np.maximum(valid_widths - 1.0, 1.0))),
        ]
        ctx[out_name] = metric_form(
            _NAMES,
            values,
            {"unit": "bp", "center_tolerance_bp": tolerance, "n_peaks": int(widths.size)},
        )
        self._export_data = {
            "output": out_name,
            "n_valid": int(offsets.size),
            "mean_center_deviation": float(np.mean(center_deviation)),
        }
