"""Estimate R0 from the early exponential growth rate and a generation time."""

from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._epi_common import metric_form, numeric_column
from src.task.step.steps._epi_common import metric_form, numeric_column, time_values, simulate_sir, simulate_seir

class EpidemicR0Step(Step):
    provider = "operon-core"
    parameters_file = "epidemic_r0.EpidemicR0Step.parameters.json"

    definition = {'protocol_revision': '3.7', 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}, 'protocol_version': 3, 'id': 'epidemic_r0', 'version': '1.0.0', 'kind': 'operator', 'title': 'Basic reproduction number from growth', 'description': 'Estimate R0 from the early exponential growth rate and a generation time.', 'category': 'Epidemiology', 'icon': 'ChartLine', 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'dims': [{'param': 'time_dim', 'default': 'time'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': [], 'ndim': 2, 'info': {'missing_code': {'type': ['number', 'null']}}}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True, 'info': {'missing_code': {'type': ['number', 'null']}}}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'inputs_arity': 1, 'outputs': [], 'output_parameter': 'output'}

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return cls.full_estimate(inputs, params, profiles)

    def run(self, ctx: Context, inputs):
        form = inputs[0]
        out_name = str(ctx.step_params.get("output") or "epidemic_r0_result")
        time_dim = str(ctx.step_params.get("time_dim") or "time")
        field_dim = str(ctx.step_params.get("field_dim") or "field")
        t = time_values(form, time_dim)
        cases_field = str(ctx.step_params.get("cases_field") or "cases")
        y = numeric_column(form, field_dim, cases_field)
        window = int(ctx.step_params.get("window_days") or 30)
        tg = float(ctx.step_params.get("generation_time_days") or 5.0)
        if tg <= 0:
            raise StepError("epidemic_r0: generation time must be positive")
        pos = np.flatnonzero(y > 0)
        if pos.size < 3:
            raise StepError("epidemic_r0: fewer than three positive points")
        start = int(pos[0])
        tt = t[start:min(start + window, y.size)]
        yy = y[start:min(start + window, y.size)]
        keep = yy > 0
        slope = float(np.polyfit(tt[keep], np.log(yy[keep]), 1)[0])
        r0 = 1.0 + slope * tg
        values = [round(r0, 8), round(slope, 8), round(tg, 8)]
        ctx[out_name] = metric_form(['r0', 'growth_rate_per_day', 'generation_time_days'], values)
        self._export_data = {"output": out_name}
