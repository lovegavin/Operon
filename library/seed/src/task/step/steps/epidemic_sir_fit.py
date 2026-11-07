"""Fit a closed SIR model to an incidence series by least squares."""

from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._epi_common import metric_form, numeric_column
from src.task.step.steps._epi_common import metric_form, numeric_column, time_values, simulate_sir, simulate_sir

class EpidemicSirFitStep(Step):
    provider = "operon-core"
    parameters_file = "epidemic_sir_fit.EpidemicSirFitStep.parameters.json"

    definition = {'protocol_revision': '3.7', 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}, 'protocol_version': 3, 'id': 'epidemic_sir_fit', 'version': '1.0.0', 'kind': 'operator', 'title': 'SIR model fit', 'description': 'Fit a closed SIR model to an incidence series by least squares.', 'category': 'Epidemiology', 'icon': 'ChartLine', 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'dims': [{'param': 'time_dim', 'default': 'time'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': [], 'ndim': 2, 'info': {'missing_code': {'type': ['number', 'null']}}}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True, 'info': {'missing_code': {'type': ['number', 'null']}}}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'inputs_arity': 1, 'outputs': [], 'output_parameter': 'output'}

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return cls.full_estimate(inputs, params, profiles)

    def run(self, ctx: Context, inputs):
        form = inputs[0]
        out_name = str(ctx.step_params.get("output") or "epidemic_sir_fit_result")
        time_dim = str(ctx.step_params.get("time_dim") or "time")
        field_dim = str(ctx.step_params.get("field_dim") or "field")
        t = time_values(form, time_dim)
        cases_field = str(ctx.step_params.get("cases_field") or "cases")
        y = numeric_column(form, field_dim, cases_field)
        n_pop = float(ctx.step_params.get("population_size") or 1_000_000)
        if n_pop <= y.max():
            raise StepError("SIR: population must exceed the largest incidence")
        from scipy.optimize import least_squares

        def residual(p):
            beta, gamma, i0 = p
            pred = simulate_sir(t, n_pop, beta, gamma, i0)
            return (pred - y) / np.sqrt(np.maximum(y, 1.0))

        best = None
        i0_guess = max(1.0, float(y[0]))
        for beta0 in (0.25, 0.5, 0.9):
            for gamma0 in (0.05, 0.1, 0.2):
                fit = least_squares(
                    residual, x0=[beta0, gamma0, i0_guess],
                    bounds=([0.01, 0.01, 0.1], [5.0, 2.0, n_pop * 0.2]),
                    max_nfev=600)
                if best is None or fit.cost < best.cost:
                    best = fit
        beta, gamma, i0 = [float(v) for v in best.x]
        rmse = float(np.sqrt(np.mean((simulate_sir(t, n_pop, beta, gamma, i0) - y) ** 2)))
        values = [round(beta, 8), round(gamma, 8), round(beta / gamma, 8), round(rmse, 8), float(y.sum())]
        ctx[out_name] = metric_form(['beta', 'gamma', 'r0', 'rmse', 'total_cases'], values)
        self._export_data = {"output": out_name}
