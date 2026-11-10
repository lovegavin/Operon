"""Shared helpers for methylation panel operators."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError


def _labels(form, dim):
    return (form.labels or {}).get(dim) or {}


def decode_column(form, field_dim, name, operator="methylation"):
    labels = _labels(form, field_dim)
    if name not in labels:
        raise StepError(f"{operator}: column '{name}' is required")
    values = np.asarray(form.data[:, labels[name]])
    encoder = ((form.info or {}).get("encoders") or {}).get(field_dim, {}).get(name)
    inverse = getattr(encoder, "inverse", None)
    if callable(inverse):
        return [str(value) for value in inverse(values.astype(int))]
    if isinstance(encoder, dict):
        return [str(encoder.get(int(value), value)) for value in values]
    return [str(value) for value in values]


def numeric_column(form, field_dim, name, operator="methylation"):
    labels = _labels(form, field_dim)
    if name not in labels:
        raise StepError(f"{operator}: column '{name}' is required")
    values = np.asarray(form.data[:, labels[name]], dtype=float)
    if values.size and np.any(~np.isfinite(values)):
        raise StepError(f"{operator}: column '{name}' contains non-finite values")
    return values


def probe_form(names, columns, probe_labels, info=None):
    data = np.column_stack([np.asarray(v, dtype=float) for v in columns])
    labels = {
        "probe": {str(k): int(v) for k, v in probe_labels.items()},
        "statistic": {name: i for i, name in enumerate(names)},
    }
    return Form(data=data, dims=["probe", "statistic"], labels=labels, info={"missing_code": np.nan})
