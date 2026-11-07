"""Shared helpers for the b69 immune-repertoire operators."""
from __future__ import annotations
import numpy as np
from src.core import Form


def column_index(form, dim, name):
    labels = form.labels.get(dim, {})
    if name not in labels:
        raise ValueError(f"column {name!r} is not present on {dim!r}")
    return int(labels[name])


def numeric_column(form, dim, name):
    return np.asarray(form.data[:, column_index(form, dim, name)], dtype=float)


def string_column(form, dim, name):
    idx = column_index(form, dim, name)
    raw = form.data[:, idx]
    spec = (form.info or {}).get("encoders", {}).get(dim, {}).get(name)
    if spec is None:
        return [str(v) for v in raw]
    if hasattr(spec, "inverse_transform"):
        return [str(v) for v in spec.inverse_transform(raw.astype(int))]
    if isinstance(spec, dict):
        return [str(spec.get(str(int(v)), v)) for v in raw]
    return [str(v) for v in raw]


def result_form(names, values, columns):
    entry = {}
    for i, n in enumerate(names):
        key = str(n)
        if key in entry:
            key = f"{key}#{i}"
        entry[key] = i
    out = Form(
        data=np.asarray(values, dtype=float),
        dims=["entry", "statistic"],
        labels={"entry": entry, "statistic": {c: i for i, c in enumerate(columns)}},
        info={"missing_code": np.nan, "columns": list(columns)},
    )
    out.validate()
    return out
