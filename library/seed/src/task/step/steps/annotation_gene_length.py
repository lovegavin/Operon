"""Gene length profile."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._annot_common import (matrix_form, numeric, row_names,
                                               strings)



class AnnotationGeneLengthStep(Step):
    provider = "operon-core"
    parameters_file = "annotation_gene_length.AnnotationGeneLengthStep.parameters.json"

    definition = {
        "protocol_revision": "3.7",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
        "protocol_version": 3,
        "id": "annotation_gene_length",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Gene length profile",
        "description": "Per-gene length, log length and short/long flags from a gene table.",
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

        starts = numeric(form, field_dim, "start", "annotation_gene_length")
        ends = numeric(form, field_dim, "end", "annotation_gene_length")
        length = ends - starts
        if np.any(length < 0):
            raise StepError("annotation_gene_length: end must be >= start")
        short_bp = int(ctx.step_params.get("short_bp", 500))
        long_bp = int(ctx.step_params.get("long_bp", 2000))
        columns = {
            "length_bp": length,
            "log10_length": np.log10(np.maximum(length, 1.0)),
            "is_short": (length <= short_bp).astype(float),
            "is_long": (length >= long_bp).astype(float),
        }
        ctx[out_name] = matrix_form(row_dim, names, columns, {"unit": "bp"})
