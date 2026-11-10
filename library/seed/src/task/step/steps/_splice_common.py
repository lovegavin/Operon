"""Shared helpers for the b73 splicing panel."""

from __future__ import annotations

import numpy as np
from src.core import Form


def _label_map(form, dim):
    labels = form.labels.get(dim, {})
    if not isinstance(labels, dict):
        raise ValueError(f"dimension {dim!r} must carry a label mapping")
    return labels


def names_for(form, dim):
    labels = _label_map(form, dim)
    return [str(k) for k, _ in sorted(labels.items(), key=lambda kv: kv[1])]


def numeric_column(form, dim, name):
    axis = [d for d in form.dims if d != dim][0]
    labels = _label_map(form, axis)
    if name not in labels:
        raise ValueError(f"column {name!r} is missing from dimension {axis!r}")
    return np.asarray(form.data[:, labels[name]], dtype=float)


def result_form(row_dim, row_names, columns, values, info=None):
    data = np.asarray(values, dtype=float).reshape(len(row_names), len(columns))
    labels = {row_dim: {str(n): i for i, n in enumerate(row_names)},
              "statistic": {str(n): i for i, n in enumerate(columns)}}
    return Form(data=data, dims=[row_dim, "statistic"], labels=labels,
                info=dict(info or {}, missing_code=np.nan))
