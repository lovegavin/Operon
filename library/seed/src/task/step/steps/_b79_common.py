"""Shared helpers for the b79 methylation and tree-distance operators."""
from __future__ import annotations

import numpy as np

from src.core.forms.form import Form


def field_index(form, name):
    labels = (form.labels or {}).get(form.dims[1]) or {}
    if name not in labels:
        raise ValueError("missing column %r" % name)
    return int(labels[name])


def numeric(form, name):
    return np.asarray(form.data[:, field_index(form, name)], dtype=float)


def strings(form, name):
    column = np.asarray(form.data[:, field_index(form, name)])
    encoders = ((form.info or {}).get("encoders") or {}).get(form.dims[1]) or {}
    spec = encoders.get(name)
    if spec is None:
        return [str(v) for v in column]
    if isinstance(spec, dict):
        return [str(spec[int(v)]) for v in column]
    inverse = getattr(spec, "inverse_transform", None)
    if callable(inverse):
        return [str(v) for v in inverse(column.astype(int))]
    mapping = getattr(spec, "inverse", None)
    if isinstance(mapping, dict):
        return [str(mapping[int(v)]) for v in column]
    classes = getattr(spec, "classes_", None)
    if classes is not None:
        return [str(classes[int(v)]) for v in column]
    return [str(v) for v in column]


def table(names, values, columns):
    data = np.asarray(values, dtype=float)
    if data.ndim == 1:
        data = data.reshape(1, -1)
    return Form(
        data=data,
        dims=["row", "statistic"],
        labels={
            "row": {name: i for i, name in enumerate(names)},
            "statistic": {name: i for i, name in enumerate(columns)},
        },
        info={"columns": list(columns)},
    )
