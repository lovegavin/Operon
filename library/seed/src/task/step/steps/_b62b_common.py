"""Shared helpers for the b62b spectra/epitope panel."""
import numpy as np
from src.core import Form


def field_dim(form):
    return [d for d in form.dims if d != form.dims[0]][0]


def column(form, name):
    fd = field_dim(form)
    idx = (form.labels.get(fd, {}) or {}).get(name)
    if idx is None:
        raise ValueError("missing column %s" % name)
    return np.asarray(form.data[:, int(idx)], dtype=float)


def string_column(form, name):
    fd = field_dim(form)
    idx = (form.labels.get(fd, {}) or {}).get(name)
    if idx is None:
        raise ValueError("missing column %s" % name)
    enc = (form.info.get("encoders") or {}).get(fd, {}).get(name)
    raw = form.data[:, int(idx)]
    if enc is None:
        return [str(int(v)) for v in raw]
    if hasattr(enc, "inverse_transform"):
        return list(enc.inverse_transform(raw.astype(int)))
    if isinstance(enc, dict):
        return [enc.get(int(v), str(int(v))) for v in raw]
    if callable(enc):
        return [enc(int(v)) for v in raw]
    return [str(int(v)) for v in raw]


def table(rows, cols, data):
    return Form(
        data=np.round(np.asarray(data, dtype=float), 9),
        dims=["row", "statistic"],
        labels={"row": {str(k): i for i, k in enumerate(rows)},
                "statistic": {c: i for i, c in enumerate(cols)}},
        info={},
    )
