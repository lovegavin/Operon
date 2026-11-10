"""Shared helpers for the b81 population-genetics operators."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form


def form_labels(form, dim):
    labels = (form.labels or {}).get(dim) or {}
    return [key for key, _ in sorted(labels.items(), key=lambda item: int(item[1]))]


def _decoder(spec):
    if spec is None:
        return None
    inverse = getattr(spec, "inverse", None)
    if isinstance(inverse, dict):
        return lambda value: inverse[int(value)]
    if hasattr(spec, "inverse_transform"):
        return lambda value: spec.inverse_transform([int(value)])[0]
    return None


def _column_decoders(form, dim):
    encoders = (form.info or {}).get("encoders") or {}
    per_column = encoders.get(dim) or {}
    names = form_labels(form, dim)
    out = []
    for name in names:
        spec = per_column.get(name)
        if spec is None and len(per_column) == 1:
            spec = next(iter(per_column.values()))
        out.append(_decoder(spec))
    return out


def read_strings(form, row_dim, field_dim):
    if list(form.dims) != [row_dim, field_dim]:
        raise StepError("expected dims [{}, {}], got {}".format(row_dim, field_dim, list(form.dims)))
    decoders = _column_decoders(form, field_dim)
    names = form_labels(form, row_dim)
    data = np.asarray(form.data)
    sequences = []
    for i, name in enumerate(names):
        cells = []
        for j in range(data.shape[1]):
            value = data[i, j]
            decoder = decoders[j] if j < len(decoders) else None
            cells.append(str(decoder(value)) if decoder is not None else str(value))
        sequences.append((name, "".join(cells)))
    return sequences


def table(names, rows, columns):
    labels = {
        "entry": {name: idx for idx, name in enumerate(names)},
        "statistic": {name: idx for idx, name in enumerate(columns)},
    }
    out = Form(
        data=np.round(np.asarray(rows, dtype=np.float64), 9),
        dims=["entry", "statistic"],
        labels=labels,
        info={"format": "table"},
    )
    out.validate()
    return out
