"""Shared helpers for b75b operators."""
import numpy as np
from src.core import Form


def row_names(form, dim):
    labels = form.labels.get(dim, {}) or {}
    if labels:
        return [k for k, _ in sorted(labels.items(), key=lambda kv: kv[1])]
    return [str(i) for i in range(form.data.shape[0])]


def numeric(form, dim, name):
    fields = [d for d in form.dims if d != dim][0]
    labels = form.labels.get(fields, {}) or {}
    idx = labels.get(name)
    if idx is None:
        raise ValueError("column %r not found" % name)
    return np.asarray(form.data[:, int(idx)], dtype=float)


def result_form(names, metrics, data, info=None):
    data = np.round(np.asarray(data, dtype=float), 9)
    return Form(
        data=data,
        dims=["row", "statistic"],
        labels={"row": {str(k): i for i, k in enumerate(names)},
                "statistic": {m: i for i, m in enumerate(metrics)}},
        info=dict(info or {}),
    )
