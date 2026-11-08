"""Shared helpers for the b94 causal-inference operators."""

from __future__ import annotations

import numpy as np

from src.core import Form


def matrix(form):
    return np.asarray(form.data, dtype=float)


def row_names(form):
    spec = form.labels.get(form.dims[0], {})
    if isinstance(spec, dict) and spec:
        return [str(n) for n, _ in sorted(spec.items(), key=lambda x: x[1])]
    return [str(i) for i in range(form.data.shape[0])]


def column(form, name, dim=None):
    axis = dim or form.dims[1]
    spec = form.labels.get(axis, {})
    if not isinstance(spec, dict) or name not in spec:
        raise ValueError(f"missing column {name!r} on dim {axis!r}")
    return np.asarray(form.data[:, spec[name]], dtype=float)


def table(dim, values, columns):
    cols = list(columns)
    data = np.column_stack([np.asarray(values[c], dtype=float) for c in cols])
    return Form(
        dims=[dim, "statistic"],
        data=np.round(data, 9),
        labels={dim: {dim: 0}, "statistic": {c: i for i, c in enumerate(cols)}},
    )


def controls(form, spec):
    names = [s.strip() for s in spec.split(",") if s.strip()]
    cols = [np.asarray(form.data[:, form.labels[form.dims[1]][n]], dtype=float) for n in names]
    return cols, names
