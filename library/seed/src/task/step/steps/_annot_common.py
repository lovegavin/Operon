"""Shared helpers for the b61 annotation panel."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError


def labels(form, dim):
    raw = (form.labels or {}).get(dim, {})
    if isinstance(raw, dict):
        return {str(k): int(v) for k, v in raw.items()}
    return {str(v): i for i, v in enumerate(raw or [])}


def row_names(form, dim):
    lab = labels(form, dim)
    return [name for name, _ in sorted(lab.items(), key=lambda kv: kv[1])]


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


def matrix_form(row_dim, names, columns, info=None):
    order = list(columns)
    data = np.column_stack([np.asarray(columns[c], dtype=float) for c in order])
    labels_map = {row_dim: {name: i for i, name in enumerate(names)},
                  "statistic": {c: i for i, c in enumerate(order)}}
    label_order = {"statistic": order}
    payload = {"missing_code": np.nan}
    payload.update(info or {})
    return Form(data=data, dims=[row_dim, "statistic"], labels=labels_map,
                info=payload)
