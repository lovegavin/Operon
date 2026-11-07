"""Shared helpers for the b56 population-genetics operators."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError


def column(form, dim, name):
    labels = form.labels.get(dim) or {}
    if name not in labels:
        raise StepError(f"population genetics input: missing field {name!r} in {sorted(labels)}")
    return np.asarray(form.data[:, labels[name]], dtype=float)


def string_column(form, dim, name):
    labels = form.labels.get(dim) or {}
    if name not in labels:
        raise StepError(f"population genetics input: missing field {name!r} in {sorted(labels)}")
    values = form.data[:, labels[name]]
    enc = (form.info.get("encoders") or {}).get(dim) or {}
    spec = enc.get(name)
    if spec is not None:
        if hasattr(spec, "inverse_transform"):
            return list(spec.inverse_transform(values.astype(int)))
        if isinstance(spec, dict):
            from src.core.encoding import get_encoder

            return list(get_encoder(spec.get("encoder", "labelencoder")).inverse_transform(values.astype(int)))
    return [str(v) for v in values]


def result_form(names, columns, dim):
    data = np.column_stack([np.asarray(c, dtype=float) for c in columns])
    form = Form(
        data=data,
        dims=[dim, "statistic"],
        labels={
            dim: {str(i): i for i in range(data.shape[0])},
            "statistic": {n: i for i, n in enumerate(names)},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form
