"""Shared helpers for the b90 gradient-boosting and density-clustering panel."""
from __future__ import annotations

import numpy as np

from src.core import Form


def matrix(form) -> np.ndarray:
    data = np.asarray(form.data, dtype=float)
    if data.ndim != 2:
        raise ValueError("expected a 2D table")
    return data


def column(form, index: int) -> np.ndarray:
    return matrix(form)[:, index]


def table(values: dict, columns: list, row_name: str = "b90", digits: int = 6) -> Form:
    row = [round(float(values[c]), digits) for c in columns]
    return Form(
        data=np.asarray([row], dtype=float),
        dims=["row", "statistic"],
        labels={"row": {row_name: 0}, "statistic": {c: i for i, c in enumerate(columns)}},
    )
