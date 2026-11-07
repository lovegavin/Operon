"""Shared helpers for the b64 single-cell panel."""
from __future__ import annotations

import numpy as np
from src.core import Form


def matrix(form):
    return np.asarray(form.data, dtype=float)


def row_names(form, dim):
    labels = form.labels.get(dim, {})
    if isinstance(labels, dict) and labels:
        return [k for k, _ in sorted(labels.items(), key=lambda kv: kv[1])]
    return [str(i) for i in range(form.data.shape[form.dims.index(dim)])]


def result_form(row_dim, names, stats, data, info=None):
    payload = {"missing_code": np.nan}
    if info:
        payload.update(info)
    out = Form(data=np.asarray(data, dtype=float), dims=[row_dim, "statistic"],
               labels={row_dim: {n: i for i, n in enumerate(names)},
                       "statistic": {s: i for i, s in enumerate(stats)}},
               info=payload)
    out.validate()
    return out
