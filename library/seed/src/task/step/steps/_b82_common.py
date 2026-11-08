"""Shared helpers for the b82 statistical-learning operators."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form


def row_names(form):
    labels = (form.labels or {}).get("row") or {}
    return [key for key, _ in sorted(labels.items(), key=lambda item: int(item[1]))]


def column(form, index):
    data = np.asarray(form.data, dtype=np.float64)
    if data.ndim != 2 or index >= data.shape[1]:
        raise StepError("expected a 2D table with column {}".format(index))
    return data[:, index]


def table(names, rows, columns):
    labels = {
        "entry": {name: idx for idx, name in enumerate(names)},
        "statistic": {name: idx for idx, name in enumerate(columns)},
    }
    out = Form(
        data=np.round(np.asarray(rows, dtype=np.float64), 9),
        dims=["entry", "statistic"],
        labels=labels,
        info={"format": "table"},
    )
    out.validate()
    return out
