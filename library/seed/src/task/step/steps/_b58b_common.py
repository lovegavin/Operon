"""Shared helpers for microbial abundance table operators."""
import numpy as np
from src.core import Form


def strings(form, dim):
    labels = form.labels.get(dim, {}) or {}
    if labels:
        return [k for k, _ in sorted(labels.items(), key=lambda kv: kv[1])]
    names = [d for d in form.dims if d != dim][0]
    labels = form.labels.get(names, {}) or {}
    inv = (form.info.get("encoders", {}) or {}).get(names, {})
    out = []
    for i in range(form.data.shape[0]):
        v = int(form.data[i, 0])
        spec = inv.get(names)
        if spec is None:
            out.append(str(v))
        elif isinstance(spec, dict):
            out.append(str(spec.get(v, v)))
        else:
            out.append(str(spec.inverse([v])[0]))
    return out


def matrix_form(names, columns, data, info=None):
    data = np.asarray(data, dtype=float)
    columns = list(columns)
    if len(columns) != data.shape[1]:
        columns = [str(c) if i < len(columns) else "s%d" % i for i, c in enumerate(columns)]
        columns += ["s%d" % i for i in range(len(columns), data.shape[1])]
    labels = {"taxon": {str(n): i for i, n in enumerate(names)},
              "sample": {str(c): i for i, c in enumerate(columns)}}
    out = Form(data=data, dims=["taxon", "sample"], labels=labels, info=dict(info or {}))
    out.validate()
    return out
