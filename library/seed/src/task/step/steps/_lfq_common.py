"""Shared helpers for label-free quantification matrix operators."""
from __future__ import annotations

import numpy as np


def matrix(form):
    data = np.asarray(form.data, dtype=float)
    if data.ndim != 2:
        raise ValueError("expected a 2D protein x sample matrix")
    return data


def labels(form):
    return {k: dict(v) if isinstance(v, dict) else v for k, v in form.labels.items()}


def stats_form(Form, names, values, protein_dim, sample_dim, info=None):
    data = np.asarray(values, dtype=float).reshape(1, -1)
    payload = {"matrix_kind": "lfq_statistics"}
    if isinstance(info, dict):
        payload.update(info)
    out = Form(data=data, dims=["metric", "statistic"],
               labels={"metric": {"value": 0}, "statistic": {n: i for i, n in enumerate(names)}},
               info=payload)
    out.validate()
    return out
