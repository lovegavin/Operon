"""Change-point detection by exact penalised segmentation"""

from __future__ import annotations

import math

import numpy as np

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.base import Step

from ._b82_common import column, row_names, table


class ChangepointPeltStep(Step):
    parameters_file = "changepoint_pelt.ChangepointPeltStep.parameters.json"

    definition = {'protocol_version': 3, 'protocol_revision': '3.7', 'id': 'changepoint_pelt', 'version': '1.0.0', 'kind': 'operator', 'title': 'Change-point detection by exact penalised segmentation', 'description': 'Exact penalised least-squares segmentation of a univariate series.', 'category': 'Statistics', 'icon': 'ChartLine', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'dependencies': ['numpy>=1.24'], 'dependency_imports': [], 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return (48 * 1024 * 1024, 0)

    def run(self, ctx, inputs):
        params = ctx.step_params
        penalty = float(params.get("penalty", 3.0))
        min_size = int(params.get("min_size", 2))
        if penalty <= 0 or min_size < 1:
            raise StepError("penalty must be positive and min_size >= 1")
        form = inputs[0]
        x = column(form, form.data.shape[1] - 1)
        n = int(x.size)
        if n < 2 * min_size:
            raise StepError("series is too short for the requested min_size")
        prefix = np.concatenate([[0.0], np.cumsum(x)])
        prefix2 = np.concatenate([[0.0], np.cumsum(x * x)])

        def cost(i, j):
            count = j - i
            total = prefix[j] - prefix[i]
            square = prefix2[j] - prefix2[i]
            return float(square - total * total / count)

        best = np.full(n + 1, np.inf)
        best[0] = -penalty
        previous = np.zeros(n + 1, dtype=int)
        for j in range(min_size, n + 1):
            for i in range(0, j - min_size + 1):
                value = best[i] + cost(i, j) + penalty
                if value < best[j]:
                    best[j] = value
                    previous[j] = i
        cuts = []
        end = n
        while end > 0:
            start = int(previous[end])
            cuts.append((start, end))
            end = start
        cuts.reverse()
        rows = []
        entry = []
        for index, (start, end) in enumerate(cuts):
            segment = x[start:end]
            entry.append("segment_{}".format(index))
            rows.append([float(start), float(end), float(end - start), float(segment.mean()), float(segment.std())])
        ctx[str(params.get("output", "output"))] = table(
            entry, rows, ["start_index", "end_index", "length", "mean", "std"]
        )
