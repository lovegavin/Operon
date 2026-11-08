"""Shared helpers for the b88 deep-learning batch."""
from __future__ import annotations
import numpy as np
from src.core import Form


def matrix(form):
    return np.asarray(form.data, dtype=float)


def labels(form, dim):
    return form.labels.get(dim, {})


def table(names, cols):
    keys = list(cols)
    rows = len(next(iter(cols.values())))
    data = np.zeros((rows, len(keys)), dtype=float)
    for j, k in enumerate(keys):
        data[:, j] = np.round(np.asarray(cols[k], dtype=float), 3)
    return Form(data=data, dims=["entry", "statistic"],
                labels={"entry": {str(n): i for i, n in enumerate(names)},
                        "statistic": {k: j for j, k in enumerate(keys)}}, info={})
