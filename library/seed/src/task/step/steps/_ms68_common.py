"""Shared helpers for b68 LC-MS feature operators."""
from __future__ import annotations

import numpy as np

from src.core import Form


ELEMENTS = {
    "C": [(12.0, 0.9893), (13.003354835, 0.0107)],
    "H": [(1.007825032, 0.999885), (2.014101778, 0.000115)],
    "N": [(14.003074, 0.99636), (15.000109, 0.00364)],
    "O": [(15.994915, 0.99757), (16.999132, 0.00038), (17.99916, 0.00205)],
    "S": [(31.972071, 0.9499), (32.971459, 0.0075), (33.967867, 0.0425), (35.967081, 0.0001)],
    "P": [(30.973762, 1.0)],
}
PROTON = 1.007276466621


def column(form, dim, name):
    labels = form.labels.get(dim)
    if labels is None:
        raise ValueError(f"missing dimension {dim!r}")
    if isinstance(labels, dict):
        if name not in labels:
            raise ValueError(f"missing field {name!r}")
        return np.asarray(form.data[:, labels[name]], dtype=float)
    raise ValueError("field labels must be a mapping")


def row_labels(form, dim):
    labels = form.labels[dim]
    if isinstance(labels, dict):
        return [str(k) for k in labels]
    return [str(v) for v in labels]


def group_index(form, dim):
    labels = form.labels[dim]
    if isinstance(labels, dict):
        return np.asarray([labels[str(v)] if str(v) in labels else i
                           for i, v in enumerate(form.data[:, 0])], dtype=int)
    return np.arange(form.shape[0], dtype=int)


def tabular(dims, labels, data, name, info=None):
    out = Form(data=np.asarray(data, dtype=float), dims=dims, labels=labels,
               info={"missing_code": float("nan"), **({name: info} if info else {})})
    out.validate()
    return out
