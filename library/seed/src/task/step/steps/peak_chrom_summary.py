"""Chromosome-level concentration of narrowPeak intervals."""

from __future__ import annotations

from collections import Counter

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._peak_common import decode_column, metric_form

_NAMES = [
    "n_peaks",
    "n_chromosomes",
    "max_peaks_per_chromosome",
    "mean_peaks_per_chromosome",
    "median_peaks_per_chromosome",
    "fraction_top_chromosome",
    "fraction_top3_chromosomes",
]


class PeakChromSummaryStep(Step):
    provider = "operon-core"
    parameters_file = "peak_chrom_summary.PeakChromSummaryStep.parameters.json"

    definition = {
        "protocol_revision": "3.7",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
        "protocol_version": 3,
        "id": "peak_chrom_summary",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Peak chromosome concentration",
        "description": "Summarize how narrowPeak intervals distribute over chromosomes.",
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
        chromosomes = decode_column(form, field_dim, "chrom", "peak_chrom_summary")
        if not chromosomes:
            raise StepError("peak_chrom_summary: no peaks in input")
        counts = Counter(chromosomes)
        values_sorted = sorted(counts.values(), reverse=True)
        total = float(len(chromosomes))
        n_chrom = float(len(counts))
        top3 = float(sum(values_sorted[:3])) / total
        values = [
            total,
            n_chrom,
            float(values_sorted[0]),
            float(np.mean(values_sorted)),
            float(np.median(values_sorted)),
            float(values_sorted[0]) / total,
            top3,
        ]
        ctx[out_name] = metric_form(_NAMES, values, {"n_peaks": int(total)})
        self._export_data = {"output": out_name, "n_chromosomes": int(n_chrom)}
