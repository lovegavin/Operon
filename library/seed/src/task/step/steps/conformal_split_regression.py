"""Split conformal prediction intervals for regression"""

from __future__ import annotations

import math

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step

from ._b82_common import column, row_names, table


class ConformalSplitRegressionStep(Step):
    parameters_file = "conformal_split_regression.ConformalSplitRegressionStep.parameters.json"

    definition = {'protocol_version': 3, 'protocol_revision': '3.7', 'id': 'conformal_split_regression', 'version': '1.0.0', 'kind': 'operator', 'title': 'Split conformal prediction intervals for regression', 'description': 'Distribution-free split-conformal regression intervals with finite-sample coverage.', 'category': 'Machine Learning', 'icon': 'ChartLine', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'dependencies': ['numpy>=1.24'], 'dependency_imports': [], 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (24 * 1024 * 1024, 0)

    def run(self, ctx, inputs):
        params = ctx.step_params
        alpha = float(params.get("alpha", 0.1))
        if not 0.0 < alpha < 1.0:
            raise StepError("alpha must be in (0, 1)")
        form = inputs[0]
        y = column(form, 0)
        pred = column(form, 1)
        phase = column(form, 2)
        cal = phase == 0
        test = ~cal
        if int(cal.sum()) < 2 or int(test.sum()) < 1:
            raise StepError("need at least two calibration and one test row")
        residuals = np.abs(y[cal] - pred[cal])
        n = int(cal.sum())
        level = math.ceil((n + 1) * (1.0 - alpha)) / n
        level = min(1.0, max(0.0, level))
        q = float(np.quantile(residuals, level, method="higher"))
        names = row_names(form)
        rows = []
        entry = []
        covered = 0
        for idx in np.flatnonzero(test):
            low = float(pred[idx] - q)
            high = float(pred[idx] + q)
            hit = 1.0 if low <= y[idx] <= high else 0.0
            covered += int(hit)
            entry.append(names[idx] if idx < len(names) else str(idx))
            rows.append([float(y[idx]), float(pred[idx]), low, high, high - low, hit])
        ctx[str(params.get("output", "output"))] = table(
            entry, rows, ["y_true", "y_pred", "lower", "upper", "width", "covered"]
        )
