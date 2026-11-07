"""Association between narrowPeak width and signal."""

from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._peak_common import metric_form, numeric_column

_NAMES = [
    "n_peaks",
    "pearson_r",
    "spearman_rho",
    "slope_bp_per_signal",
    "intercept_bp",
    "mean_width",
    "mean_signal",
]


def _ranks(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=float)
    ranks[order] = np.arange(1, len(values) + 1, dtype=float)
    # average ties
    sorted_values = values[order]
    index = 0
    while index < len(sorted_values):
        end = index + 1
        while end < len(sorted_values) and sorted_values[end] == sorted_values[index]:
            end += 1
        if end - index > 1:
            ranks[order[index:end]] = 0.5 * (index + 1 + end)
        index = end
    return ranks


class PeakWidthSignalCorrelationStep(Step):
    provider = "operon-core"
    parameters_file = "peak_width_signal_correlation.PeakWidthSignalCorrelationStep.parameters.json"

    definition = {
        "protocol_revision": "3.7",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
        "protocol_version": 3,
        "id": "peak_width_signal_correlation",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Peak width versus signal",
        "description": "Correlate narrowPeak widths with signalValue.",
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
        starts = numeric_column(form, field_dim, "start", "peak_width_signal_correlation")
        ends = numeric_column(form, field_dim, "end", "peak_width_signal_correlation")
        signal = numeric_column(form, field_dim, "signalValue", "peak_width_signal_correlation")
        widths = ends - starts
        if widths.size < 2:
            raise StepError("peak_width_signal_correlation: at least two peaks are required")
        if np.any(widths < 0):
            raise StepError("peak_width_signal_correlation: end must be >= start")
        if np.std(widths) == 0 or np.std(signal) == 0:
            raise StepError("peak_width_signal_correlation: width and signal must both vary")
        r = float(np.corrcoef(widths, signal)[0, 1])
        rho = float(np.corrcoef(_ranks(widths), _ranks(signal))[0, 1])
        slope, intercept = np.polyfit(signal, widths, 1)
        values = [
            float(widths.size),
            r,
            rho,
            float(slope),
            float(intercept),
            float(np.mean(widths)),
            float(np.mean(signal)),
        ]
        # Round stored statistics to suppress BLAS-version last-bit drift across platforms.
        values = [
            float(v) if i == 0 else round(float(v), 8)
            for i, v in enumerate(values)
        ]
        ctx[out_name] = metric_form(_NAMES, values, {"n_peaks": int(widths.size)})
        self._export_data = {"output": out_name, "pearson_r": r, "spearman_rho": rho}
