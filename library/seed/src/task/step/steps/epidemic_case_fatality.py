"""Compute the crude case fatality ratio with a Wilson confidence interval."""

from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._epi_common import metric_form, numeric_column
from src.task.step.steps._epi_common import metric_form, numeric_column, time_values, simulate_sir, simulate_seir

class EpidemicCaseFatalityStep(Step):
    provider = "operon-core"
    parameters_file = "epidemic_case_fatality.EpidemicCaseFatalityStep.parameters.json"

    definition = {'protocol_revision': '3.7', 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}, 'protocol_version': 3, 'id': 'epidemic_case_fatality', 'version': '1.0.0', 'kind': 'operator', 'title': 'Case fatality ratio', 'description': 'Compute the crude case fatality ratio with a Wilson confidence interval.', 'category': 'Epidemiology', 'icon': 'ChartLine', 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'dims': [{'param': 'time_dim', 'default': 'time'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': [], 'ndim': 2, 'info': {'missing_code': {'type': ['number', 'null']}}}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True, 'info': {'missing_code': {'type': ['number', 'null']}}}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'inputs_arity': 1, 'outputs': [], 'output_parameter': 'output'}

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return cls.full_estimate(inputs, params, profiles)

    def run(self, ctx: Context, inputs):
        form = inputs[0]
        out_name = str(ctx.step_params.get("output") or "epidemic_case_fatality_result")
        time_dim = str(ctx.step_params.get("time_dim") or "time")
        field_dim = str(ctx.step_params.get("field_dim") or "field")
        cases_field = str(ctx.step_params.get("cases_field") or "cases")
        deaths_field = str(ctx.step_params.get("deaths_field") or "deaths")
        cases = numeric_column(form, field_dim, cases_field)
        deaths = numeric_column(form, field_dim, deaths_field)
        total_cases = float(cases.sum())
        total_deaths = float(deaths.sum())
        if total_cases <= 0:
            raise StepError("epidemic_case_fatality: no cases")
        cfr = total_deaths / total_cases
        z = float(ctx.step_params.get("z") or 1.959963984540054)
        denom = 1.0 + z * z / total_cases
        centre = (cfr + z * z / (2 * total_cases)) / denom
        half = z * np.sqrt(cfr * (1 - cfr) / total_cases + z * z / (4 * total_cases ** 2)) / denom
        values = [round(cfr, 8), round(max(0.0, centre - half), 8), round(min(1.0, centre + half), 8), total_deaths, total_cases]
        ctx[out_name] = metric_form(['cfr', 'ci_low', 'ci_high', 'deaths', 'cases'], values)
        self._export_data = {"output": out_name}
