"""Gini coefficient and summary statistics for a non-negative numeric vector."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.task.step.base import Step

from ._b81_common import table

STATISTICS = ("gini", "n", "total", "mean")


def gini_summary(values) -> dict:
    """Return the Gini coefficient of non-negative values and its summary statistics."""
    finite = np.asarray(values, dtype=np.float64).ravel()
    finite = finite[np.isfinite(finite)]
    if finite.size and float(finite.min()) < 0.0:
        raise StepError("numeric_gini_coefficient: values must be non-negative")
    n = int(finite.size)
    total = float(finite.sum()) if n else 0.0
    mean = total / n if n else 0.0
    if n == 0 or mean <= 0.0:
        return {"gini": 0.0, "n": float(n), "total": total, "mean": mean}
    ordered = np.sort(finite)
    positions = np.arange(1, n + 1, dtype=np.float64)
    gini = float(np.sum((2.0 * positions - n - 1.0) * ordered) / (n * total))
    return {"gini": gini, "n": float(n), "total": total, "mean": mean}


class NumericGiniCoefficientStep(Step):
    provider = "operon-core"
    parameters_file = "numeric_gini_coefficient.NumericGiniCoefficientStep.parameters.json"

    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "numeric_gini_coefficient",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Gini coefficient",
        "description": "Computes the Gini coefficient, count, total and mean of a non-negative numeric vector.",
        "category": "Statistics",
        "icon": "ChartLine",
        "inputs_arity": 1,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [{
                "version": 1,
                "numeric": True,
                "ndim": 1,
                "dims": [{"param": "value_dim", "default": "value"}],
                "labels": [],
                "parallel": [],
            }],
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True,
                },
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
    }

    def run(self, ctx, inputs) -> None:
        if not inputs:
            raise StepError("numeric_gini_coefficient: a numeric vector input is required")
        form = inputs[0]
        params = ctx.step_params
        value_dim = str(params.get("value_dim") or "value")
        out_name = str(params.get("output") or "gini_coefficient")

        if form.data.ndim != 1 or list(form.dims) != [value_dim]:
            raise StepError(
                "numeric_gini_coefficient: a 1-D numeric form with dims "
                f"[{value_dim}] is required, got {list(form.dims)}"
            )

        summary = gini_summary(form.data)
        ctx[out_name] = table(
            ["gini"],
            [[summary["gini"], summary["n"], summary["total"], summary["mean"]]],
            list(STATISTICS),
        )
