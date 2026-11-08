"""Site occupancy computed from modified and unmodified peptide intensities."""

from __future__ import annotations

import math

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


def _decode(form, dim, name):
    column = np.asarray(form.data[:, field_index(form, dim, name)])
    encoders = ((form.info or {}).get("encoders") or {}).get(dim) or {}
    spec = encoders.get(name)
    if spec is None:
        return [str(int(value)) if float(value).is_integer() else str(value) for value in column]
    inverse = getattr(spec, "inverse_transform", None)
    if callable(inverse):
        return [str(value) for value in inverse(column.astype(int))]
    mapping = getattr(spec, "inverse", None)
    if isinstance(mapping, dict):
        return [str(mapping[int(value)]) for value in column]
    if callable(mapping):
        return [str(value) for value in mapping(column.astype(int))]
    classes = getattr(spec, "classes_", None)
    if classes is not None:
        return [str(classes[int(value)]) for value in column]
    raise StepError("cannot decode column %r" % name)


def strings(form, dim, name):
    return _decode(form, dim, name)


def form_labels(form, dim):
    labels = (form.labels or {}).get(dim) or {}
    return [key for key, _ in sorted(labels.items(), key=lambda item: int(item[1]))]


def result(dims, labels, rows, info=None):
    out = Form(data=np.round(np.asarray(rows, dtype=np.float64), 9), dims=list(dims),
               labels=labels, info=dict(info or {}))
    out.validate()
    return out


class PtmOccupancyStep(Step):
    parameters_file = "ptm_occupancy.PtmOccupancyStep.parameters.json"

    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "ptm_occupancy",
        "version": "1.0.0",
        "kind": "operator",
        "title": "PTM site occupancy",
        "description": "Site occupancy computed from modified and unmodified peptide intensities.",
        "category": "Proteomics",
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
                        {"param": "row_dim", "default": "site"},
                        {"param": "field_dim", "default": "field"}
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
        row_dim = str(params.get("row_dim", "site"))
        field_dim = str(params.get("field_dim", "field"))
        out_name = str(params.get("output", "occupancy"))
        form = inputs[0]
        if list(form.dims) != [row_dim, field_dim]:
            raise StepError("ptm_occupancy: unexpected dims %s" % (list(form.dims),))
        names = form_labels(form, row_dim)
        modified = numeric_column(form, field_dim, "modified")
        unmodified = numeric_column(form, field_dim, "unmodified")
        if np.any(modified < 0.0) or np.any(unmodified < 0.0):
            raise StepError("ptm_occupancy: intensities must be non-negative")
        rows = []
        for mod, unmod in zip(modified, unmodified):
            total = float(mod) + float(unmod)
            rows.append([float(mod), float(unmod), float(mod) / total if total > 0.0 else float("nan")])
        labels = {"site": {name: idx for idx, name in enumerate(names)},
                  "statistic": {"n_modified": 0, "n_unmodified": 1, "occupancy": 2}}
        ctx[out_name] = result(["site", "statistic"], labels, rows, {"method": "ratio"})
