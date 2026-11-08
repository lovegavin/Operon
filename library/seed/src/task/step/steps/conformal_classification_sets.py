"""Split conformal prediction sets for binary classification"""

from __future__ import annotations

import math

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step

from ._b82_common import column, row_names, table


class ConformalClassificationSetsStep(Step):
    parameters_file = "conformal_classification_sets.ConformalClassificationSetsStep.parameters.json"

    definition = {'protocol_version': 3, 'protocol_revision': '3.7', 'id': 'conformal_classification_sets', 'version': '1.0.0', 'kind': 'operator', 'title': 'Split conformal prediction sets for binary classification', 'description': 'Split-conformal binary prediction sets with a calibrated score threshold.', 'category': 'Machine Learning', 'icon': 'ChartLine', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'dependencies': ['numpy>=1.24'], 'dependency_imports': [], 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

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
        score = column(form, 1)
        phase = column(form, 2)
        cal = phase == 0
        test = ~cal
        if int(cal.sum()) < 2 or int(test.sum()) < 1:
            raise StepError("need at least two calibration and one test row")
        true_score = np.where(y[cal] >= 0.5, score[cal], 1.0 - score[cal])
        n = int(cal.sum())
        level = math.ceil((n + 1) * (1.0 - alpha)) / n
        level = min(1.0, max(0.0, level))
        q = float(np.quantile(1.0 - true_score, level, method="higher"))
        threshold = 1.0 - q
        names = row_names(form)
        rows = []
        entry = []
        for idx in np.flatnonzero(test):
            p1 = float(score[idx])
            in_zero = (1.0 - p1) >= threshold
            in_one = p1 >= threshold
            members = int(in_zero) + int(in_one)
            label = 1.0 if in_one else 0.0
            hit = 1.0 if (int(y[idx]) == 1 and in_one) or (int(y[idx]) == 0 and in_zero) else 0.0
            entry.append(names[idx] if idx < len(names) else str(idx))
            rows.append([float(y[idx]), p1, threshold, float(members), label, hit])
        ctx[str(params.get("output", "output"))] = table(
            entry, rows, ["y_true", "score", "threshold", "set_size", "predicted_label", "covered"]
        )
