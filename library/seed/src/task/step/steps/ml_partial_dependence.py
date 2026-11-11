"""Partial dependence curve."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step

from ._b84_common import matrix, row_names


class MlPartialDependenceStep(Step):
    parameters_file = "ml_partial_dependence.MlPartialDependenceStep.parameters.json"
    definition = {'protocol_version': 3, 'protocol_revision': '3.7', 'kind': 'operator', 'id': 'ml_partial_dependence', 'version': '1.0.0', 'title': 'Partial dependence curve', 'description': 'Ridge-model partial dependence for one feature on a grid.', 'category': 'Machine Learning', 'icon': 'image', 'inputs_arity': 2, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}, {'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'value_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': False, 'dims': [{'param': 'grid_dim', 'default': 'grid'}, {'param': 'statistic', 'default': 'statistic'}], 'labels': {'statistic': ['feature_value', 'mean_prediction']}}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}, {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    def run(self, ctx, inputs):
        x = matrix(inputs[0])
        y = matrix(inputs[1]).reshape(-1)
        n, p = x.shape
        if n == 0 or p == 0 or y.size != n:
            raise StepError("ml_partial_dependence: design matrix and response are inconsistent")
        if not 0 <= int(ctx.step_params.get("feature", 0)) < p:
            raise StepError("ml_partial_dependence: feature index is out of range")
        lam = float(ctx.step_params.get("alpha", 1.0))
        feat = int(ctx.step_params.get("feature", 0))
        n_grid = int(ctx.step_params.get("n_grid", 5))
        a = np.column_stack([np.ones(n), x])
        gram = a.T @ a + lam * np.eye(p + 1)
        gram[0, 0] -= lam
        coef = np.linalg.solve(gram, a.T @ y)
        vals = np.linspace(float(x[:, feat].min()), float(x[:, feat].max()), n_grid)
        rows = []
        base = x.copy()
        for v in vals:
            base[:, feat] = v
            pred = np.column_stack([np.ones(n), base]) @ coef
            rows.append([float(v), float(pred.mean())])
        out = Form(np.asarray(rows, dtype=float),
                   dims=["grid", "statistic"],
                   labels={"grid": {"g%d" % i: i for i in range(n_grid)},
                           "statistic": {"feature_value": 0, "mean_prediction": 1}})
        ctx[ctx.step_params["output"]] = out
