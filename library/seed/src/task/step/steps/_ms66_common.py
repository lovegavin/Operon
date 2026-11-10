"""Shared helpers for the b66 proteomics MS operators."""
from __future__ import annotations

import numpy as np
from src.core import Form


def field_index(form, dim, name):
    labels = form.labels.get(dim, {})
    if name in labels:
        return int(labels[name])
    raise ValueError(f"column {name!r} is not present on axis {dim!r}")


def numeric_column(form, dim, name):
    return np.asarray(form.data[:, field_index(form, dim, name)], dtype=float)


def string_column(form, dim, name):
    idx = field_index(form, dim, name)
    raw = form.data[:, idx]
    info = (form.info or {}).get("encoders", {}).get(dim, {})
    spec = info.get(name)
    if spec is None:
        return [str(v) for v in raw]
    if hasattr(spec, "inverse_transform"):
        return [str(v) for v in spec.inverse_transform(raw.astype(int))]
    if isinstance(spec, dict):
        return [str(spec.get(str(int(v)), v)) for v in raw]
    return [str(v) for v in raw]


def result_form(names, values, columns, info=None):
    payload = {"missing_code": np.nan, "columns": list(columns)}
    if info:
        payload.update(info)
    out = Form(
        data=np.asarray(values, dtype=float),
        dims=["entry", "statistic"],
        labels={"entry": {str(n): i for i, n in enumerate(names)},
                "statistic": {c: i for i, c in enumerate(columns)}},
        info=payload,
    )
    out.validate()
    return out
