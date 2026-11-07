"""Shared helpers for b68 LC-MS annotation operators."""
from __future__ import annotations

import numpy as np


def field_index(form, dim):
    for d in form.dims:
        if d != dim:
            return d
    raise ValueError("form needs a second dimension")


def labels_for(form, dim):
    other = field_index(form, dim)
    return other, form.labels.get(other, {})


def numeric_column(form, dim, name):
    other, labels = labels_for(form, dim)
    if name not in labels:
        raise ValueError(f"column {name!r} is not present on {other!r}")
    return np.asarray(form.data[:, labels[name]], dtype=float)


def string_column(form, dim, name):
    other, labels = labels_for(form, dim)
    if name not in labels:
        raise ValueError(f"column {name!r} is not present on {other!r}")
    col = form.data[:, labels[name]]
    enc = form.info.get("encoders", {}).get(other, {})
    if isinstance(enc, dict) and name in enc:
        spec = enc[name]
        inv = getattr(spec, "inverse", None) or getattr(spec, "inverse_transform", None)
        if isinstance(inv, dict):
            return [str(inv.get(int(v), v)) for v in col]
        if callable(inv):
            return [str(v) for v in inv(np.asarray(col))]
        if isinstance(spec, dict):
            return [str(spec.get(int(v), v)) for v in col]
    return [str(v) for v in col]


def result_form(names, rows, info=None, columns=None):
    from src.core import Form
    data = np.asarray(rows, dtype=float)
    if data.ndim == 1:
        data = data.reshape(-1, 1)
    if columns is None:
        columns = [f"stat{i}" for i in range(data.shape[1])]
    return Form(data=data, dims=["entry", "statistic"],
                labels={"entry": {n: i for i, n in enumerate(names)},
                        "statistic": {n: i for i, n in enumerate(columns)}},
                info=info or {})
