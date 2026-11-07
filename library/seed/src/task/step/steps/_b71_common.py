"""Shared helpers for b71 comparative-genomics operators."""
from __future__ import annotations
import numpy as np
from src.core import Form


def matrix(form):
    return np.asarray(form.data, dtype=float)


def row_names(form):
    labels = form.labels.get(form.dims[0], {})
    return [str(k) for k, _ in sorted(labels.items(), key=lambda kv: kv[1])]


def result_form(names, rows, columns):
    labels = {}
    for i, n in enumerate(names):
        key = str(n)
        if key in labels:
            key = f"{key}#{i}"
        labels[key] = i
    out = Form(data=np.asarray(rows, dtype=float), dims=["entry", "statistic"],
               labels={"entry": labels, "statistic": {c: i for i, c in enumerate(columns)}},
               info={"missing_code": np.nan, "columns": list(columns)})
    out.validate()
    return out
