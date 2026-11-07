"""Shared helpers for the epidemiology operators."""

from __future__ import annotations

import numpy as np
from scipy.integrate import solve_ivp

from src.core import StepError, Form


def numeric_column(form, field_dim: str, name: str) -> np.ndarray:
    labels = form.labels.get(field_dim) or {}
    if name not in labels:
        raise StepError(f"epidemiology input: missing field {name!r}")
    col = np.asarray(form.data[:, labels[name]], dtype=float)
    if col.size < 3:
        raise StepError("epidemiology input: fewer than three time points")
    return col


def time_values(form, time_dim: str) -> np.ndarray:
    labels = form.labels.get(time_dim) or {}
    if not labels:
        return np.arange(form.data.shape[0], dtype=float)
    inv = {pos: key for key, pos in labels.items()}
    out = []
    for i in range(form.data.shape[0]):
        try:
            out.append(float(inv[i]))
        except (KeyError, ValueError) as exc:
            raise StepError("epidemiology input: time labels must be numeric") from exc
    return np.asarray(out, dtype=float)


def metric_form(names, values, info=None):
    names = [str(n) for n in names]
    data = np.asarray(values, dtype=float).reshape(1, -1)
    form = Form(data=data, dims=["metric", "statistic"],
                labels={"metric": {"value": 0}, "statistic": {n: i for i, n in enumerate(names)}},
                info={"missing_code": np.nan})
    if info:
        form.info.update(info)
    form.validate()
    return form


def _clean(incidence):
    y = np.asarray(incidence, dtype=float)
    if not np.isfinite(y).all():
        raise StepError("epidemiology input: incidence contains non-finite values")
    if (y < 0).any():
        raise StepError("epidemiology input: incidence must be non-negative")
    return y


def simulate_sir(t, n_pop, beta, gamma, i0):
    t = np.asarray(t, dtype=float)
    y0 = [max(n_pop - i0, 0.0), i0, 0.0]
    def rhs(_t, y):
        s, i, r = y
        new = beta * s * i / n_pop
        return [-new, new - gamma * i, gamma * i]
    sol = solve_ivp(rhs, (float(t.min()), float(t.max())), y0, t_eval=t,
                    rtol=1e-7, atol=1e-9, method="RK45")
    if not sol.success:
        raise StepError("SIR integration failed")
    s, i, r = sol.y
    return beta * s * i / n_pop


def simulate_seir(t, n_pop, beta, sigma, gamma, i0):
    t = np.asarray(t, dtype=float)
    y0 = [max(n_pop - i0, 0.0), 0.0, i0, 0.0]
    def rhs(_t, y):
        s, e, i, r = y
        new = beta * s * i / n_pop
        return [-new, new - sigma * e, sigma * e - gamma * i, gamma * i]
    sol = solve_ivp(rhs, (float(t.min()), float(t.max())), y0, t_eval=t,
                    rtol=1e-7, atol=1e-9, method="RK45")
    if not sol.success:
        raise StepError("SEIR integration failed")
    s, e, i, r = sol.y
    return beta * s * i / n_pop
