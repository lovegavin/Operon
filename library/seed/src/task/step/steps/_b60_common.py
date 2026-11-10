"""Shared numeric helpers for b60 metagenomics summaries."""
from __future__ import annotations

import numpy as np
from src.core import Form, StepError


def numeric(form, dim, name, op):
    lab = (form.labels or {}).get(dim) or {}
    if name not in lab:
        raise StepError(f"{op}: column '{name}' is required")
    v = np.asarray(form.data[:, lab[name]], dtype=float)
    if v.size and np.any(~np.isfinite(v)):
        raise StepError(f"{op}: column '{name}' contains non-finite values")
    return v


def row_form(names, rows, row_dim, row_labels, info=None):
    payload = {"missing_code": np.nan}
    payload.update(info or {})
    return Form(data=np.asarray(rows, dtype=float), dims=[row_dim, "statistic"],
                labels={row_dim: row_labels, "statistic": {n: i for i, n in enumerate(names)}},
                info=payload)
