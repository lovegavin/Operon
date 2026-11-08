"""Shared helpers for the b95 operators."""

from __future__ import annotations

import numpy as np

from src.core import Form


def matrix(form):
    return np.asarray(form.data, dtype=float)


def column(form, name, dim=None):
    axis = dim or form.dims[1]
    spec = form.labels.get(axis, {})
    if not isinstance(spec, dict) or name not in spec:
        raise ValueError(f"missing column {name!r}")
    return np.asarray(form.data[:, spec[name]], dtype=float)


def columns(form, spec):
    names = [s.strip() for s in spec.split(",") if s.strip()]
    return [column(form, n) for n in names], names


def table(dim, row_labels, values, stat_names=None):
    cols = stat_names or list(values)
    data = np.column_stack([np.asarray(values[c], dtype=float) for c in cols])
    return Form(dims=[dim, "statistic"], data=np.round(data, 9),
                labels={dim: {str(n): i for i, n in enumerate(row_labels)},
                        "statistic": {c: i for i, c in enumerate(cols)}})
