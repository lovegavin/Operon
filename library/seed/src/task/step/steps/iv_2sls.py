"""Instrumental-variables 2SLS (b94)."""

from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._b94_common import column, controls, matrix, row_names, table


class Iv2slsStep(Step):
    parameters_file = "iv_2sls.Iv2slsStep.parameters.json"
    definition = {'id': 'iv_2sls', 'version': '1.0.0', 'title': 'Instrumental-variables 2SLS', 'description': 'Two-stage least squares estimate of a single endogenous regressor with one instrument and optional controls.', 'category': 'Causal inference', 'icon': 'causal', 'protocol_version': 3, 'protocol_revision': '3.7', 'kind': 'operator', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    def run(self, ctx, inputs):
        yc = ctx.step_params["y_column"]
        xc = ctx.step_params["endog_column"]
        zc = ctx.step_params["instrument_column"]
        y = column(inputs[0], yc)
        x = column(inputs[0], xc)
        z = column(inputs[0], zc)
        ctrl, _ = controls(inputs[0], ctx.step_params.get("control_columns", ""))
        n = y.shape[0]
        X = np.column_stack([np.ones(n)] + ctrl + [x])
        Z = np.column_stack([np.ones(n)] + ctrl + [z])
        k = X.shape[1]
        if n <= k + 1:
            raise ValueError("need more observations than regressors")
        zz = Z.T @ Z
        if np.linalg.matrix_rank(zz) < k:
            raise ValueError("instrument matrix is rank deficient")
        Xh = Z @ np.linalg.solve(zz, Z.T @ X)
        xx = Xh.T @ Xh
        if np.linalg.matrix_rank(xx) < k:
            raise ValueError("first-stage fitted regressors are collinear")
        beta = np.linalg.solve(xh := (Xh.T @ Xh), Xh.T @ y)
        resid = y - X @ beta
        sigma2 = float(resid @ resid) / (n - k)
        cov = sigma2 * np.linalg.inv(xh)
        se = float(np.sqrt(cov[-1, -1]))
        coef = float(beta[-1])
        t = coef / se
        from scipy import stats as st
        p = float(2.0 * st.t.sf(abs(t), n - k))
        crit = float(st.t.ppf(0.975, n - k))
        vals = {"coef": [coef], "stderr": [se], "t": [t], "p": [p],
                "ci_low": [coef - crit * se], "ci_high": [coef + crit * se], "n": [float(n)]}
        out = table("stat", vals, ["coef", "stderr", "t", "p", "ci_low", "ci_high", "n"])
        ctx[ctx.step_params["output"]] = out
