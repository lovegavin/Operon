"""Shared helpers for b59 metagenomics panels."""
from __future__ import annotations

import numpy as np
from src.core import Form, StepError


def labels(form, dim):
    return (form.labels or {}).get(dim) or {}


def numeric(form, dim, name, op):
    lab = labels(form, dim)
    if name not in lab:
        raise StepError(f"{op}: column '{name}' is required")
    values = np.asarray(form.data[:, lab[name]], dtype=float)
    if values.size and np.any(~np.isfinite(values)):
        raise StepError(f"{op}: column '{name}' contains non-finite values")
    return values


def strings(form, dim, name, op):
    lab = labels(form, dim)
    if name not in lab:
        raise StepError(f"{op}: column '{name}' is required")
    values = np.asarray(form.data[:, lab[name]])
    enc = ((form.info or {}).get("encoders") or {}).get(dim, {})
    spec = enc.get(name) if isinstance(enc, dict) else None
    inv = getattr(spec, "inverse", None)
    if isinstance(inv, dict):
        return [str(inv.get(int(v), v)) for v in values]
    if callable(inv):
        return [str(x) for x in inv(values.astype(int))]
    if isinstance(spec, dict):
        return [str(spec.get(int(v), v)) for v in values]
    return [str(int(v)) if float(v).is_integer() else str(v) for v in values]


def out_form(names, values, info=None):
    info = dict(info or {})
    info.setdefault("missing_code", np.nan)
    return Form(
        data=np.asarray(values, dtype=float).reshape(1, -1),
        dims=["statistic"],
        labels={"statistic": {n: i for i, n in enumerate(names)}},
        info=info,
    )


def row_form(names, rows, row_dim, row_labels, info=None):
    info = dict(info or {})
    info.setdefault("missing_code", np.nan)
    return Form(
        data=np.asarray(rows, dtype=float),
        dims=[row_dim, "statistic"],
        labels={row_dim: row_labels, "statistic": {n: i for i, n in enumerate(names)}},
        info=info,
    )
