"""Shared helpers for the b55 population-genetics operators."""
import numpy as np
from src.core import Form
from src.task.step.base import Step


def column_index(form, dim, name):
    labels = form.labels.get(dim, {})
    if name not in labels:
        raise ValueError("column %r is not present on %r" % (name, dim))
    return int(labels[name])


def numeric_column(form, dim, name):
    return np.asarray(form.data[:, column_index(form, dim, name)], dtype=float)


def row_names(form):
    dim = form.dims[0]
    labels = form.labels.get(dim, {})
    if labels:
        return [k for k, _ in sorted(labels.items(), key=lambda kv: kv[1])]
    return [str(i) for i in range(form.data.shape[0])]


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


def table(names, values, columns):
    out = Form(
        data=np.round(np.asarray(values, dtype=float), 9),
        dims=["entry", "statistic"],
        labels={"entry": {str(n): i for i, n in enumerate(names)},
                "statistic": {c: i for i, c in enumerate(columns)}},
        info={"columns": list(columns)},
    )
    out.validate()
    return out
