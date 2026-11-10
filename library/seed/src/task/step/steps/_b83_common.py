"""Shared helpers for the b83 batch."""
from __future__ import annotations

import numpy as np
from src.core import Form


def column(form: Form, index: int) -> np.ndarray:
    return np.asarray(form.data[:, index], dtype=float)


def strings(form: Form, dim: str, name: str) -> list[str]:
    labels = form.labels.get(dim) or {}
    if name not in labels:
        raise ValueError(f"missing column {name!r} in dim {dim!r}")
    index = labels[name]
    enc = (form.info.get("encoders") or {}).get(dim, {}).get(name)
    out = []
    for value in form.data[:, index]:
        if enc is None:
            out.append(str(value))
        elif hasattr(enc, "inverse_transform"):
            out.append(str(enc.inverse_transform([int(value)])[0]))
        elif hasattr(enc, "inverse"):
            inverse = enc.inverse
            out.append(str(inverse[int(value)] if isinstance(inverse, dict) else inverse(int(value))))
        else:
            out.append(str(value))
    return out


def table(entry, rows, columns):
    return Form(np.round(np.asarray(rows, dtype=float), 9), dims=["entry", "statistic"], labels={"entry": {str(e): i for i, e in enumerate(entry)}, "statistic": {c: j for j, c in enumerate(columns)}})


def named_column(form: Form, name: str) -> np.ndarray:
    labels = form.labels.get(form.dims[1]) or {}
    if name not in labels:
        raise ValueError(f"missing field {name!r}")
    return column(form, labels[name])


def feature_matrix(form: Form, excluded: set[str]) -> np.ndarray:
    labels = form.labels.get(form.dims[1]) or {}
    keep = [i for n, i in labels.items() if n not in excluded]
    keep.sort()
    return np.asarray(form.data[:, keep], dtype=float)
