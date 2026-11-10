"""Per-protein iBAQ from peptide intensities: summed intensity divided by the number of observable peptides."""

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


class ProteomicsIbaqStep(Step):
    parameters_file = "proteomics_ibaq.ProteomicsIbaqStep.parameters.json"

    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "proteomics_ibaq",
        "version": "1.0.0",
        "kind": "operator",
        "title": "iBAQ protein abundance",
        "description": "Per-protein iBAQ from peptide intensities: summed intensity divided by the number of observable peptides.",
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
                        {"param": "row_dim", "default": "row"},
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
        row_dim = str(params.get("row_dim", "row"))
        field_dim = str(params.get("field_dim", "field"))
        out_name = str(params.get("output", "ibaq"))
        form = inputs[0]
        if list(form.dims) != [row_dim, field_dim]:
            raise StepError("proteomics_ibaq: unexpected dims %s" % (list(form.dims),))
        protein = strings(form, field_dim, "protein")
        peptide = strings(form, field_dim, "peptide")
        intensity = numeric_column(form, field_dim, "intensity")
        if np.any(intensity < 0.0):
            raise StepError("proteomics_ibaq: intensities must be non-negative")
        groups = {}
        for key, seq, value in zip(protein, peptide, intensity):
            entry = groups.setdefault(key, {"peptides": set(), "total": 0.0})
            entry["peptides"].add(seq)
            entry["total"] += float(value)
        names = sorted(groups)
        rows = []
        for name in names:
            entry = groups[name]
            count = len(entry["peptides"])
            rows.append([float(count), entry["total"], entry["total"] / count if count else float("nan")])
        labels = {"protein": {name: idx for idx, name in enumerate(names)},
                  "statistic": {"n_peptides": 0, "total_intensity": 1, "ibaq": 2}}
        ctx[out_name] = result(["protein", "statistic"], labels, rows, {"method": "ibaq"})
