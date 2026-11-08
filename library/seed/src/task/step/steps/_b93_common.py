"""Shared helpers for b93 time-series and anomaly operators."""
from __future__ import annotations
import numpy as np
from src.core import Form


def matrix(form):
    return np.asarray(form.data, dtype=float)


def column(form, name):
    labels = form.labels.get(form.dims[1], {}) if len(form.dims) > 1 else {}
    if name in labels:
        idx = labels[name]
    else:
        idx = int(name)
    return np.asarray(form.data[:, idx], dtype=float)


def row_names(form):
    labels = form.labels.get(form.dims[0], {})
    if isinstance(labels, dict) and labels:
        inv = {v: k for k, v in labels.items()}
        return [str(inv.get(i, i)) for i in range(form.data.shape[0])]
    return [str(i) for i in range(form.data.shape[0])]


def table(dim_name, row_labels, values, columns=None):
    cols = columns or list(values.keys())
    data = np.column_stack([np.asarray(values[c], dtype=float) for c in cols])
    labels = {dim_name: {str(l): i for i, l in enumerate(row_labels)},
              "statistic": {c: i for i, c in enumerate(cols)}}
    return Form(data=np.round(data, 9), dims=[dim_name, "statistic"], labels=labels)
