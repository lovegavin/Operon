"""Shared helpers for narrowPeak geometry operators."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError


def _labels(form, dim):
    return (form.labels or {}).get(dim) or {}


def decode_column(form, field_dim, name, operator="peak"):
    """Return a decoded string column from a tabular form."""

    labels = _labels(form, field_dim)
    if name not in labels:
        raise StepError(f"{operator}: column '{name}' is required")
    values = np.asarray(form.data[:, labels[name]])
    encoder = ((form.info or {}).get("encoders") or {}).get(field_dim, {}).get(name)
    inverse = getattr(encoder, "inverse", None)
    if isinstance(inverse, dict):
        return [str(inverse.get(int(value), value)) for value in values]
    if callable(inverse):
        return [str(value) for value in inverse(values.astype(int))]
    if isinstance(encoder, dict):
        return [str(encoder.get(int(value), value)) for value in values]
    inverse_transform = getattr(encoder, "inverse_transform", None)
    if callable(inverse_transform):
        return [str(value) for value in inverse_transform(values.astype(int))]
    decoded = []
    for value in values:
        if isinstance(value, (float, np.floating)) and float(value).is_integer():
            decoded.append(str(int(value)))
        else:
            decoded.append(str(value))
    return decoded


def numeric_column(form, field_dim, name, operator="peak"):
    """Return a finite numeric column from a tabular form."""

    labels = _labels(form, field_dim)
    if name not in labels:
        raise StepError(f"{operator}: column '{name}' is required")
    values = np.asarray(form.data[:, labels[name]], dtype=float)
    if values.size and np.any(~np.isfinite(values)):
        raise StepError(f"{operator}: column '{name}' contains non-finite values")
    return values


def metric_form(names, values, info=None):
    """Build the [metric, statistic] numeric form used by the panel."""

    data = np.asarray(values, dtype=np.float64).reshape(-1, 1)
    labels = {
        "metric": {name: index for index, name in enumerate(names)},
        "statistic": {"value": 0},
    }
    payload = {"missing_code": np.nan, "n_metrics": len(names)}
    if isinstance(info, dict):
        payload.update(info)
    return Form(data=data, dims=["metric", "statistic"], labels=labels, info=payload)
