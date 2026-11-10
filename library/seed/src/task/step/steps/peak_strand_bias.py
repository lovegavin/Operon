"""Strand balance of narrowPeak intervals."""

from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._peak_common import decode_column, metric_form

_NAMES = [
    "n_peaks",
    "n_plus",
    "n_minus",
    "n_unknown",
    "fraction_plus",
    "plus_minus_ratio",
]


class PeakStrandBiasStep(Step):
    provider = "operon-core"
    parameters_file = "peak_strand_bias.PeakStrandBiasStep.parameters.json"

    definition = {
        "protocol_revision": "3.7",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
        "protocol_version": 3,
        "id": "peak_strand_bias",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Peak strand balance",
        "description": "Count plus, minus and unstranded narrowPeak intervals.",
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
        strands = decode_column(form, field_dim, "strand", "peak_strand_bias")
        if not strands:
            raise StepError("peak_strand_bias: no peaks in input")
        plus = sum(1 for value in strands if value in ("+", "1", "plus"))
        minus = sum(1 for value in strands if value in ("-", "-1", "minus"))
        unknown = len(strands) - plus - minus
        total = float(len(strands))
        fraction = plus / total
        ratio = float(plus) / float(minus) if minus else float("nan")
        values = [total, float(plus), float(minus), float(unknown), fraction, ratio]
        ctx[out_name] = metric_form(_NAMES, values, {"n_peaks": int(total)})
        self._export_data = {"output": out_name, "n_peaks": int(total), "fraction_plus": fraction}
