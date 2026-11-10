"""Annotation completeness."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._annot_common import (matrix_form, numeric, row_names,
                                               strings)



class AnnotationCompletenessStep(Step):
    provider = "operon-core"
    parameters_file = "annotation_completeness.AnnotationCompletenessStep.parameters.json"

    definition = {
        "protocol_revision": "3.7",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
        "protocol_version": 3,
        "id": "annotation_completeness",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Annotation completeness",
        "description": "Marker completeness per genome from presence and copy counts.",
        "category": "Genome annotation",
        "icon": "Table",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "observation_dim", "default": "observation"},
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
        row_dim = str(params.get("observation_dim", "observation"))
        field_dim = str(params.get("field_dim", "field"))
        form = inputs[0]
        names = row_names(form, row_dim)

        genomes = strings(form, field_dim, "genome", "annotation_completeness")
        present = numeric(form, field_dim, "present", "annotation_completeness")
        copies = numeric(form, field_dim, "copies", "annotation_completeness")
        grouped = {}
        for i, name in enumerate(genomes):
            grouped.setdefault(name, []).append(i)
        names = sorted(grouped)
        rows = []
        for name in names:
            idx = grouped.get(name, [])
            total = max(len(idx), 1)
            hit = float(np.sum(present[idx] > 0)) if idx else 0.0
            dup = float(np.sum(copies[idx] > 1)) if idx else 0.0
            rows.append((hit / total, float(total - hit), dup))
        values = np.asarray(rows, dtype=float)
        columns = {
            "completeness": values[:, 0],
            "n_missing": values[:, 1],
            "n_duplicated": values[:, 2],
        }
        ctx[out_name] = matrix_form(row_dim, names, columns, {})
