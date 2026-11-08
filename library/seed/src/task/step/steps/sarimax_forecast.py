"""SARIMAX time-series forecast (sarimax_forecast, b93)."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._b93_common import column, matrix, row_names, table


class SarimaxForecastStep(Step):
    parameters_file = "sarimax_forecast.SarimaxForecastStep.parameters.json"
    definition = {'id': 'sarimax_forecast', 'version': '1.0.0', 'title': 'SARIMAX time-series forecast', 'description': 'Fits a SARIMAX model to an ordered series and returns a multi-step forecast with confidence bounds.', 'category': 'Statistics', 'icon': 'timeline', 'protocol_version': 3, 'protocol_revision': '3.7', 'kind': 'operator', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    def run(self, ctx, inputs):
        time_column = ctx.step_params.get("time_column", "time")
        value_column = ctx.step_params.get("value_column", "value")
        p = int(ctx.step_params.get("order_p", 1))
        d = int(ctx.step_params.get("order_d", 0))
        q = int(ctx.step_params.get("order_q", 0))
        steps = int(ctx.step_params.get("steps", 3))
        alpha = float(ctx.step_params.get("alpha", 0.05))
        t = column(inputs[0], time_column)
        y = column(inputs[0], value_column)
        if y.size < 8:
            raise ValueError("need at least 8 observations")
        order = np.argsort(t)
        y = y[order]
        from statsmodels.tsa.statespace.sarimax import SARIMAX

        model = SARIMAX(y, order=(p, d, q), trend="c" if d == 0 else "n", enforce_stationarity=True, enforce_invertibility=True)
        fit = model.fit(disp=False, maxiter=200)
        fc = fit.get_forecast(steps=steps)
        mean = np.asarray(fc.predicted_mean, dtype=float)
        ci = np.asarray(fc.conf_int(alpha=alpha), dtype=float)
        names = [f"t{int(t[-1]) + i + 1}" for i in range(steps)]
        out = table("step", names, {
            "forecast": np.round(mean, 6),
            "lower": np.round(ci[:, 0], 6),
            "upper": np.round(ci[:, 1], 6),
        }, columns=["forecast", "lower", "upper"])
        ctx[ctx.step_params["output"]] = out



def _expected_path(n):
    if n <= 1:
        return 0.0
    return 2.0 * (np.log(n - 1) + 0.5772156649015329) - 2.0 * (n - 1) / n
