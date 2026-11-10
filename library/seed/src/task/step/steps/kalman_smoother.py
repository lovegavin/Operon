"""Operator: Rauch-Tung-Striebel Kalman smoother."""

from __future__ import annotations

import numpy as np

from src.core import Form
from src.core.errors import StepError
from src.task.step.base import Step
from ._b86_common import matrix, table


class KalmanSmootherStep(Step):
    parameters_file = "kalman_smoother.KalmanSmootherStep.parameters.json"

    definition = {'id': 'kalman_smoother', 'version': '1.0.0', 'title': 'Rauch-Tung-Striebel Kalman smoother', 'description': 'Run the Rauch-Tung-Striebel smoother for a local-level model and report filtered and smoothed state estimates with their variances.', 'category': 'Statistics', 'icon': 'activity', 'kind': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'dependencies': ['numpy>=1.24']}

    def run(self, ctx, inputs):
        out_name = ctx.step_params["output"]
        params = ctx.step_params
        process_var = ctx.step_params.get("process_var", 1.0)
        obs_var = ctx.step_params.get("obs_var", 1.0)

        y = matrix(inputs[0]).reshape(-1)
        q = float(params["process_var"]); r = float(params["obs_var"])
        m = np.zeros(y.size); p = np.zeros(y.size); mf = np.zeros(y.size); pf = np.zeros(y.size)
        m[0] = y[0]; p[0] = 0.5 * r
        mf[0] = m[0]; pf[0] = p[0]
        for t in range(1, y.size):
            mp = m[t - 1]; pp = p[t - 1] + q
            k = pp / (pp + r)
            m[t] = mp + k * (y[t] - mp); p[t] = (1.0 - k) * pp
            mf[t] = m[t]; pf[t] = p[t]
        ms = m.copy(); ps = p.copy()
        for t in range(y.size - 2, -1, -1):
            c = p[t] / (p[t] + q)
            ms[t] = m[t] + c * (ms[t + 1] - m[t])
            ps[t] = p[t] + c * c * (ps[t + 1] - (p[t] + q))
        names = [f"t{i}" for i in range(y.size)]
        cols = {"observed": y, "filtered_mean": mf, "filtered_var": pf, "smoothed_mean": ms, "smoothed_var": ps}
        ctx[out_name] = table(names, cols, list(cols))

