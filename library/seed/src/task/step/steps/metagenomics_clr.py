"""Centered log-ratio transform of a non-negative count table with a pseudocount."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step


def field_index(form, dim, name):
    labels = (form.labels or {}).get(dim) or {}
    if name not in labels:
        raise StepError("missing column %r in dimension %r" % (name, dim))
    return int(labels[name])


def numeric_column(form, dim, name):
    return np.asarray(form.data[:, field_index(form, dim, name)], dtype=np.float64)


def form_labels(form, dim):
    labels = (form.labels or {}).get(dim) or {}
    return [key for key, _ in sorted(labels.items(), key=lambda item: int(item[1]))]


def result(dims, labels, rows, info=None):
    out = Form(data=np.round(np.asarray(rows, dtype=np.float64), 9), dims=list(dims),
               labels=labels, info=dict(info or {}))
    out.validate()
    return out


class MetagenomicsClrStep(Step):
    parameters_file = "metagenomics_clr.MetagenomicsClrStep.parameters.json"

    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "metagenomics_clr",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Centered log-ratio transform",
        "description": "Centered log-ratio transform of a non-negative count table with a pseudocount.",
        "category": "Metagenomics",
        "icon": "Ruler",
        "inputs_arity": 1,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "ndim": 2,
                    "dims": [
                        {"param": "row_dim", "default": "sample"},
                        {"param": "field_dim", "default": "feature"},
                    ],
                    "labels": [],
                    "parallel": [],
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (32 * 1024 * 1024, 0)

    def run(self, ctx, inputs):
        params = ctx.step_params
        row_dim = str(params.get("row_dim", "sample"))
        field_dim = str(params.get("field_dim", "feature"))
        pseudocount = float(params.get("pseudocount", 0.5))
        out_name = str(params.get("output", "clr"))
        if pseudocount <= 0.0:
            raise StepError("metagenomics_clr: pseudocount must be positive")
        form = inputs[0]
        if list(form.dims) != [row_dim, field_dim]:
            raise StepError(
                "metagenomics_clr: expected dims [{}, {}], got {}".format(
                    row_dim, field_dim, list(form.dims)))
        data = np.asarray(form.data, dtype=np.float64)
        if np.any(data < 0.0):
            raise StepError("metagenomics_clr: abundances must be non-negative")
        logs = np.log(data + pseudocount)
        centred = logs - logs.mean(axis=1, keepdims=True)
        rows = form_labels(form, row_dim)
        cols = form_labels(form, field_dim)
        labels = {
            row_dim: {name: idx for idx, name in enumerate(rows)},
            field_dim: {name: idx for idx, name in enumerate(cols)},
        }
        ctx[out_name] = result([row_dim, field_dim], labels, centred,
                               {"method": "clr", "pseudocount": pseudocount})
