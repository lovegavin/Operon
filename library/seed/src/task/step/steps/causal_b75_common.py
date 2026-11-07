"""Shared helpers for the b75 causal-inference operators."""
import numpy as np
from scipy import stats

from src.core import Form


def _field(form, name):
    labels = form.labels.get("field", {})
    if name not in labels:
        raise ValueError(f"column {name!r} is not present in the field axis")
    return np.asarray(form.data[:, int(labels[name])], dtype=float)


def _has(form, name):
    return name in form.labels.get("field", {})


def ols(X, y):
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    n, k = X.shape
    xtx_inv = np.linalg.pinv(X.T @ X)
    meat = (X * (resid ** 2)[:, None]).T @ X
    cov = xtx_inv @ meat @ xtx_inv * (n / max(n - k, 1))
    se = np.sqrt(np.maximum(np.diag(cov), 0.0))
    t = beta / np.where(se > 0, se, np.inf)
    p = 2.0 * stats.norm.sf(np.abs(t))
    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return beta, se, t, p, r2


def result_form(names, values, info=None):
    data = np.asarray([(0.0 if abs(float(v)) < 1e-12 else float(f"{float(v):.10g}")) if isinstance(v, (int, float, np.floating)) else v for v in values], dtype=float).reshape(1, -1)
    labels = {"summary": {"estimate": 0}, "statistic": {str(n): i for i, n in enumerate(names)}}
    return Form(data=data, dims=["summary", "statistic"], labels=labels,
                info=dict(info or {}, missing_code=np.nan))
