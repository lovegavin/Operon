"""Shared helpers for the b65 spatial transcriptomics panel."""
import numpy as np
from src.core import Form


def column(form, dim, name):
    labels = form.labels.get(dim) or {}
    if name not in labels:
        return np.arange(form.data.shape[form.dims.index(dim)], dtype=float)
    return form.data[:, labels[name]]


def numeric(form, dim, name):
    return np.asarray(column(form, dim, name), dtype=float)


def names(form):
    labels = form.labels.get(form.dims[0]) or {}
    inv = {v: k for k, v in labels.items()}
    return [inv.get(i, str(i)) for i in range(form.data.shape[0])]


def table(rows, values, columns):
    out = Form(data=np.round(np.asarray(values, dtype=float), 9), dims=["row", "statistic"],
               labels={"row": {str(n): i for i, n in enumerate(rows)},
                       "statistic": {c: i for i, c in enumerate(columns)}},
               info={"columns": list(columns)})
    out.validate()
    return out


def matrix(names_a, names_b, values):
    out = Form(data=np.round(np.asarray(values, dtype=float), 9), dims=["row", "row2"],
               labels={"row": {str(n): i for i, n in enumerate(names_a)},
                       "row2": {str(n): i for i, n in enumerate(names_b)}})
    out.validate()
    return out


def knn(coords, k):
    n = coords.shape[0]
    if n < 2:
        raise ValueError("at least two cells are required")
    k = max(1, min(int(k), n - 1))
    d = np.sqrt(((coords[:, None, :] - coords[None, :, :]) ** 2).sum(axis=2))
    np.fill_diagonal(d, np.inf)
    idx = np.argsort(d, axis=1)[:, :k]
    dist = np.take_along_axis(d, idx, axis=1)
    return idx, dist
