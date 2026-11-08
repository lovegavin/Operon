"""Shared helpers for the b86 state-space batch."""
from __future__ import annotations

import numpy as np

from src.core import Form


def matrix(form):
    return np.asarray(form.data, dtype=float)


def named_column(form, name):
    labels = form.labels.get(form.dims[1], {})
    if name not in labels:
        raise ValueError(f"missing column {name}")
    return np.asarray(form.data[:, labels[name]], dtype=float)


def table(names, values, columns):
    rows = len(next(iter(values.values())))
    data = np.zeros((rows, len(columns)), dtype=float)
    for j, col in enumerate(columns):
        data[:, j] = np.round(np.asarray(values[col], dtype=float), 9)
    return Form(
        data=data,
        dims=["entry", "statistic"],
        labels={"entry": {str(n): i for i, n in enumerate(names)}, "statistic": {c: j for j, c in enumerate(columns)}},
        info={},
    )
