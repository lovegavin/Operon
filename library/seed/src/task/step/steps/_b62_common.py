"""Shared helpers for the b62 epigenomics panel."""
import numpy as np
from src.core import Form


def column(form, dim, name):
    labels = form.labels.get(dim) or {}
    if name not in labels:
        return np.arange(form.data.shape[form.dims.index(dim)], dtype=float)
    return form.data[:, labels[name]]


def numeric(form, dim, name):
    return np.asarray(column(form, dim, name), dtype=float)


def strings(form, dim, name):
    vals = column(form, dim, name)
    enc = ((form.info or {}).get("encoders") or {}).get(dim, {}).get(name)
    if enc is not None:
        if hasattr(enc, "inverse_transform"):
            return [str(x) for x in enc.inverse_transform(np.rint(vals).astype(int))]
        if isinstance(enc, dict):
            if enc and all(isinstance(v, (int, float)) for v in enc.values()):
                inv = {int(v): k for k, v in enc.items()}
            else:
                inv = enc
            return [str(inv.get(int(round(float(v))), int(round(float(v))))) for v in vals]
    labels = form.labels.get(dim) or {}
    inv = {v: k for k, v in labels.items()}
    return [str(inv.get(int(round(float(v))), int(round(float(v))))) for v in vals]


def names(form):
    labels = form.labels.get(form.dims[0]) or {}
    inv = {v: k for k, v in labels.items()}
    return [inv.get(i, str(i)) for i in range(form.data.shape[0])]


def table(rows, values, columns):
    out = Form(
        data=np.round(np.asarray(values, dtype=float), 9),
        dims=["row", "statistic"],
        labels={"row": {str(n): i for i, n in enumerate(rows)},
                "statistic": {c: i for i, c in enumerate(columns)}},
        info={"columns": list(columns)},
    )
    out.validate()
    return out
