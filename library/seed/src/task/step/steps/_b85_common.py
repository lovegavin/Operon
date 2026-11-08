"""Shared helpers for the b85 torch operators."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError


def matrix(form: Form) -> np.ndarray:
    data = np.asarray(form.data, dtype=float)
    if data.ndim != 2:
        raise StepError("expected a 2D numeric table")
    return data


def named_column(form: Form, name: str) -> np.ndarray:
    dim = form.dims[1]
    labels = form.labels.get(dim, {})
    if name in labels:
        return np.asarray(form.data[:, int(labels[name])], dtype=float)
    raise StepError("missing column: " + name)


def table(rows: list[list[float]], columns: list[str]) -> Form:
    data = np.round(np.asarray(rows, dtype=float), 3)
    return Form(
        data=data,
        dims=["entry", "statistic"],
        labels={"entry": {"m" + str(i): i for i in range(len(rows))}, "statistic": {c: i for i, c in enumerate(columns)}},
    )
