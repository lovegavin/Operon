"""Shared helpers for b71b operators."""
import numpy as np
from src.core import Form


def names(form, dim):
    labels = form.labels.get(dim, {}) or {}
    if labels:
        return [k for k, _ in sorted(labels.items(), key=lambda kv: kv[1])]
    return [str(i) for i in range(form.data.shape[0])]


def column(form, dim, name):
    fields = [d for d in form.dims if d != dim][0]
    idx = (form.labels.get(fields, {}) or {}).get(name)
    if idx is None:
        raise ValueError("missing column %s" % name)
    return np.asarray(form.data[:, int(idx)], dtype=float)


def table(names_, cols, values):
    return Form(
        data=np.round(np.asarray(values, dtype=float), 9),
        dims=["row", "statistic"],
        labels={"row": {str(k): i for i, k in enumerate(names_)},
                "statistic": {c: i for i, c in enumerate(cols)}},
        info={},
    )
