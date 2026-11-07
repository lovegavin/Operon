"""Signal and confidence summaries for narrowPeak records."""

from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._peak_common import metric_form, numeric_column

_NAMES = [
    "n_peaks",
    "mean_signal",
    "median_signal",
    "max_signal",
    "p95_signal",
    "mean_pvalue",
    "mean_qvalue",
    "frac_q_gt_10",
    "frac_q_gt_20",
]


class PeakSignalStatsStep(Step):
    provider = "operon-core"
    parameters_file = "peak_signal_stats.PeakSignalStatsStep.parameters.json"

    definition = {
        "protocol_revision": "3.7",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
        "protocol_version": 3,
        "id": "peak_signal_stats",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Peak signal and confidence summary",
        "description": "Summarize ENCODE narrowPeak signalValue, pValue and qValue columns.",
        "category": "Epigenomics",
        "icon": "Pulse",
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
        signal = numeric_column(form, field_dim, "signalValue", "peak_signal_stats")
        pvalue = numeric_column(form, field_dim, "pValue", "peak_signal_stats")
        qvalue = numeric_column(form, field_dim, "qValue", "peak_signal_stats")
        if signal.size == 0:
            raise StepError("peak_signal_stats: no peaks in input")
        ctx[out_name] = metric_form(
            _NAMES,
            [
                float(signal.size),
                float(np.mean(signal)),
                float(np.median(signal)),
                float(np.max(signal)),
                float(np.percentile(signal, 95)),
                float(np.mean(pvalue)),
                float(np.mean(qvalue)),
                float(np.mean(qvalue > 10)),
                float(np.mean(qvalue > 20)),
            ],
            {"n_peaks": int(signal.size), "scale": "narrowPeak -log10 values"},
        )
        self._export_data = {
            "output": out_name,
            "n_peaks": int(signal.size),
            "mean_signal": float(np.mean(signal)),
        }
