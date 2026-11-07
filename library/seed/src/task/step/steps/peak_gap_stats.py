"""Inter-peak gap distribution within chromosomes."""

from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._peak_common import decode_column, metric_form, numeric_column

_NAMES = [
    "n_gaps",
    "mean_gap",
    "median_gap",
    "max_gap",
    "frac_gap_lt_1000",
    "n_overlaps",
    "total_gap_bp",
]


class PeakGapStatsStep(Step):
    provider = "operon-core"
    parameters_file = "peak_gap_stats.PeakGapStatsStep.parameters.json"

    definition = {
        "protocol_revision": "3.7",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
        "protocol_version": 3,
        "id": "peak_gap_stats",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Inter-peak gap statistics",
        "description": "Summarize distances between consecutive narrowPeak intervals on the same chromosome.",
        "category": "Epigenomics",
        "icon": "ArrowsOutLineVertical",
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
        threshold = float(params.get("short_gap_bp", 1000))
        form = inputs[0]
        chroms = decode_column(form, field_dim, "chrom", "peak_gap_stats")
        starts = numeric_column(form, field_dim, "start", "peak_gap_stats")
        ends = numeric_column(form, field_dim, "end", "peak_gap_stats")
        gaps = []
        overlaps = 0
        previous = None
        for index in np.argsort(np.asarray([f"{c}\x00{s:020.0f}" for c, s in zip(chroms, starts)])):
            chrom = chroms[index]
            start = starts[index]
            end = ends[index]
            if previous is not None and previous[0] == chrom:
                gap = start - previous[1]
                if gap < 0:
                    overlaps += 1
                    gap = 0.0
                gaps.append(float(gap))
            previous = (chrom, end)
        if not gaps:
            raise StepError("peak_gap_stats: at least two intervals on one chromosome are required")
        values = np.asarray(gaps, dtype=float)
        ctx[out_name] = metric_form(
            _NAMES,
            [
                float(values.size),
                float(np.mean(values)),
                float(np.median(values)),
                float(np.max(values)),
                float(np.mean(values < threshold)),
                float(overlaps),
                float(np.sum(values)),
            ],
            {"unit": "bp", "short_gap_bp": threshold, "n_gaps": int(values.size)},
        )
        self._export_data = {
            "output": out_name,
            "n_gaps": int(values.size),
            "median_gap": float(np.median(values)),
        }
