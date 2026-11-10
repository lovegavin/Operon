"""Gene overlap check."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._annot_common import (matrix_form, numeric, row_names,
                                               strings)



class AnnotationOverlapCheckStep(Step):
    provider = "operon-core"
    parameters_file = "annotation_overlap_check.AnnotationOverlapCheckStep.parameters.json"

    definition = {
        "protocol_revision": "3.7",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
        "protocol_version": 3,
        "id": "annotation_overlap_check",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Gene overlap check",
        "description": "Count pairwise overlaps between gene intervals in one table.",
        "category": "Genome annotation",
        "icon": "Table",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "gene_dim", "default": "gene"},
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
        row_dim = str(params.get("gene_dim", "gene"))
        field_dim = str(params.get("field_dim", "field"))
        form = inputs[0]
        names = row_names(form, row_dim)

        starts = numeric(form, field_dim, "start", "annotation_overlap_check")
        ends = numeric(form, field_dim, "end", "annotation_overlap_check")
        if np.any(ends < starts):
            raise StepError("annotation_overlap_check: end must be >= start")
        n = starts.size
        counts = np.zeros(n, dtype=float)
        bases = np.zeros(n, dtype=float)
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                left = max(starts[i], starts[j])
                right = min(ends[i], ends[j])
                if right > left:
                    counts[i] += 1.0
                    bases[i] += float(right - left)
        length = np.maximum(ends - starts, 1.0)
        columns = {
            "n_overlaps": counts,
            "overlap_bp": bases,
            "frac_overlapped": np.clip(bases / length, 0.0, 1.0),
        }
        ctx[out_name] = matrix_form(row_dim, names, columns, {})
