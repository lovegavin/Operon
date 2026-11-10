"""Shared helpers for the b89 deep-learning panel."""
import numpy as np

from src.core import Form


def matrix(form):
    return np.asarray(form.data, dtype=float)


def named_column(form, name):
    dim = form.dims[-1]
    labels = form.labels.get(dim) or {}
    if name not in labels:
        raise ValueError(f"missing column {name}; have {sorted(labels)}")
    return np.asarray(form.data[:, labels[name]], dtype=float)


def table(values, columns):
    n = len(next(iter(values.values())))
    data = np.column_stack([np.asarray(values[c], dtype=float) for c in columns]) if n else np.zeros((0, len(columns)))
    return Form(data=np.round(data, 3), dims=["entry", "statistic"],
                labels={"entry": {"result": 0}, "statistic": {c: i for i, c in enumerate(columns)}}, info={})
