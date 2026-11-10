"""Kalman filter for a local-level state-space model"""

from __future__ import annotations

import math

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step

from ._b82_common import column, row_names, table


class KalmanLocalLevelStep(Step):
    parameters_file = "kalman_local_level.KalmanLocalLevelStep.parameters.json"

    definition = {'protocol_version': 3, 'protocol_revision': '3.7', 'id': 'kalman_local_level', 'version': '1.0.0', 'kind': 'operator', 'title': 'Kalman filter for a local-level state-space model', 'description': 'Local-level Kalman filter with filtered states and Gaussian log-likelihood.', 'category': 'Statistics', 'icon': 'ChartLine', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'dependencies': ['numpy>=1.24'], 'dependency_imports': [], 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (24 * 1024 * 1024, 0)

    def run(self, ctx, inputs):
        params = ctx.step_params
        q = float(params.get("process_variance", 1.0))
        r = float(params.get("observation_variance", 1.0))
        if q <= 0 or r <= 0:
            raise StepError("variances must be positive")
        form = inputs[0]
        y = column(form, form.data.shape[1] - 1)
        if y.size == 0:
            raise StepError("empty series")
        mean = float(y[0])
        variance = 1.0
        loglik = 0.0
        rows = []
        entry = []
        names = row_names(form)
        for t, value in enumerate(y):
            predicted_var = variance + q
            innovation = float(value) - mean
            gain = predicted_var / (predicted_var + r)
            mean = mean + gain * innovation
            variance = (1.0 - gain) * predicted_var
            loglik += -0.5 * (math.log(2.0 * math.pi * (predicted_var + r)) + innovation * innovation / (predicted_var + r))
            entry.append(names[t] if t < len(names) else "t{}".format(t))
            rows.append([float(t), float(value), mean, variance, innovation, gain])
        ctx[str(params.get("output", "output"))] = table(
            entry, rows, ["time", "observed", "filtered_mean", "filtered_variance", "innovation", "gain"]
        )
