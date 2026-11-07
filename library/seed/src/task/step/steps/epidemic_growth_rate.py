"""Fit exponential growth to the early phase of an incidence series."""

from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._epi_common import metric_form, numeric_column
from src.task.step.steps._epi_common import metric_form, numeric_column, time_values, simulate_sir, simulate_seir

class EpidemicGrowthRateStep(Step):
    provider = "operon-core"
    parameters_file = "epidemic_growth_rate.EpidemicGrowthRateStep.parameters.json"

    definition = {'protocol_revision': '3.7', 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}, 'protocol_version': 3, 'id': 'epidemic_growth_rate', 'version': '1.0.0', 'kind': 'operator', 'title': 'Early epidemic growth rate', 'description': 'Fit exponential growth to the early phase of an incidence series.', 'category': 'Epidemiology', 'icon': 'ChartLine', 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'dims': [{'param': 'time_dim', 'default': 'time'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': [], 'ndim': 2, 'info': {'missing_code': {'type': ['number', 'null']}}}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True, 'info': {'missing_code': {'type': ['number', 'null']}}}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'inputs_arity': 1, 'outputs': [], 'output_parameter': 'output'}

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return cls.full_estimate(inputs, params, profiles)

    def run(self, ctx: Context, inputs):
        form = inputs[0]
        out_name = str(ctx.step_params.get("output") or "epidemic_growth_rate_result")
        time_dim = str(ctx.step_params.get("time_dim") or "time")
        field_dim = str(ctx.step_params.get("field_dim") or "field")
        t = time_values(form, time_dim)
        cases_field = str(ctx.step_params.get("cases_field") or "cases")
        y = numeric_column(form, field_dim, cases_field)
        window = int(ctx.step_params.get("window_days") or 30)
        pos = np.flatnonzero(y > 0)
        if pos.size < 3:
            raise StepError("epidemic_growth_rate: fewer than three positive points")
        start = int(pos[0])
        stop = min(start + window, y.size)
        tt = t[start:stop]
        yy = y[start:stop]
        keep = yy > 0
        tt, yy = tt[keep], yy[keep]
        if tt.size < 3:
            raise StepError("epidemic_growth_rate: insufficient positive window")
        slope, intercept = np.polyfit(tt, np.log(yy), 1)
        pred = slope * tt + intercept
        ss_res = float(np.sum((np.log(yy) - pred) ** 2))
        ss_tot = float(np.sum((np.log(yy) - np.log(yy).mean()) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        values = [round(slope, 8), round(float(np.log(2.0) / slope) if slope > 0 else np.nan, 8), round(r2, 8), tt.size]
        ctx[out_name] = metric_form(['growth_rate_per_day', 'doubling_time_days', 'r_squared', 'n_points'], values)
        self._export_data = {"output": out_name}
