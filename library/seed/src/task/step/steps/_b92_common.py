"""Shared helpers for the b92 causal-forest operators."""

from __future__ import annotations

import numpy as np

from src.core import Form


def matrix(form):
    return np.asarray(form.data, dtype=float)


def row_names(form):
    spec = form.labels.get(form.dims[0], {})
    if isinstance(spec, dict) and spec:
        ordered = sorted(spec.items(), key=lambda item: item[1])
        return [str(name) for name, _ in ordered]
    return [str(i) for i in range(form.data.shape[0])]


def column(form, name, dim=None):
    axis = dim or form.dims[1]
    spec = form.labels.get(axis, {})
    idx = spec[name] if isinstance(spec, dict) and name in spec else None
    if idx is None:
        raise ValueError(f"missing column {name!r} on dim {axis!r}")
    return np.asarray(form.data[:, idx], dtype=float)


def table(names, values, columns):
    if len(names) == 1:
        names = [names[0], "statistic"]
    cols = list(columns)
    data = np.column_stack([np.asarray(values[c], dtype=float) for c in cols])
    return Form(
        dims=[names[0], names[1]],
        data=np.round(data, 6),
        labels={names[0]: {names[0]: 0}, names[1]: {c: i for i, c in enumerate(cols)}},
    )


def design(form, drop):
    """Feature matrix with the named columns removed."""
    spec = form.labels.get(form.dims[1], {})
    if not isinstance(spec, dict) or not spec:
        raise ValueError("input table needs named columns")
    keep = [name for name in spec if name not in drop]
    keep.sort(key=lambda name: spec[name])
    return np.column_stack([np.asarray(form.data[:, spec[name]], dtype=float) for name in keep]), keep
