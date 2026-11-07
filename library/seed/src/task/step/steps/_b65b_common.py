import numpy as np
from src.core import Form


def _labels(form, dim):
    lab = (form.labels or {}).get(dim) or {}
    if isinstance(lab, dict):
        return {str(k): int(v) for k, v in lab.items()}
    return {str(x): i for i, x in enumerate(lab)}


def names(form):
    lab = _labels(form, form.dims[0])
    if lab:
        return [k for k, _ in sorted(lab.items(), key=lambda kv: kv[1])]
    return [f"r{i}" for i in range(form.data.shape[0])]


def strings(form, dim, column):
    lab = _labels(form, dim)
    enc = ((form.info or {}).get("encoders") or {}).get(dim) or {}
    e = enc.get(column)
    idx = lab.get(column, 0)
    vals = form.data[:, idx]
    if e is not None:
        try:
            if hasattr(e, "inverse_transform"):
                return [str(x) for x in e.inverse_transform(vals.astype(int))]
            if isinstance(e, dict):
                inv = {v: k for k, v in e.items()}
                return [str(inv.get(int(v), v)) for v in vals]
        except Exception:
            pass
    return [str(v) for v in vals]


def numeric(form, dim, column):
    idx = _labels(form, dim).get(column, 0)
    return np.asarray(form.data[:, idx], dtype=float)


def table(row_names, values, cols):
    vals = np.asarray(values, dtype=float)
    return Form(data=vals, dims=["row", "statistic"],
                labels={"row": {str(n): i for i, n in enumerate(row_names)},
                        "statistic": {str(c): i for i, c in enumerate(cols)}})


def matrix(row_names, col_names, data):
    arr = np.asarray(data, dtype=float)
    return Form(data=arr, dims=["row", "row2"],
                labels={"row": {str(n): i for i, n in enumerate(row_names)},
                        "row2": {str(c): i for i, c in enumerate(col_names)}})
