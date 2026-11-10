"""Bayesian linear regression (b95)."""

from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._b95_common import column, columns, matrix, table


class BayesianLinearRegressionStep(Step):
    parameters_file = "bayesian_linear_regression.BayesianLinearRegressionStep.parameters.json"
    definition = {'id': 'bayesian_linear_regression', 'version': '1.0.0', 'title': 'Bayesian linear regression', 'description': 'Gibbs sampling for a normal-inverse-gamma linear model with weakly informative priors.', 'category': 'Statistics', 'icon': 'bayes', 'protocol_version': 3, 'protocol_revision': '3.7', 'kind': 'operator', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    def run(self, ctx, inputs):
        y = column(inputs[0], ctx.step_params["y_column"])
        cov, names = columns(inputs[0], ctx.step_params["covariate_columns"])
        X = np.column_stack([np.ones(y.size)] + cov)
        n, k = X.shape
        n_samples = int(ctx.step_params.get("n_samples", 2000))
        burn = int(ctx.step_params.get("burn_in", 500))
        tau = float(ctx.step_params.get("prior_scale", 10.0))
        a0 = float(ctx.step_params.get("shape", 0.01))
        b0 = float(ctx.step_params.get("scale", 0.01))
        rng = np.random.default_rng(int(ctx.step_params.get("seed", 7)))
        xtx = X.T @ X
        xty = X.T @ y
        beta = np.zeros(k)
        sigma2 = float(np.var(y)) or 1.0
        keep = []
        keep_s2 = []
        for it in range(n_samples + burn):
            V = np.linalg.inv(xtx / sigma2 + np.eye(k) / tau**2)
            m = V @ xty / sigma2
            beta = rng.multivariate_normal(m, V)
            sse = float((y - X @ beta) @ (y - X @ beta))
            sigma2 = (b0 + sse / 2.0) / rng.gamma(a0 + n / 2.0)
            if it >= burn:
                keep.append(beta)
                keep_s2.append(sigma2)
        draws = np.asarray(keep)
        labels = ["(Intercept)"] + names
        vals = {"mean": draws.mean(0), "sd": draws.std(0, ddof=1),
                "ci_low": np.quantile(draws, 0.025, axis=0),
                "ci_high": np.quantile(draws, 0.975, axis=0),
                "sigma2": np.full(k, float(np.mean(keep_s2)))}
        out = table("param", labels, vals, ["mean", "sd", "ci_low", "ci_high", "sigma2"])
        ctx[ctx.step_params["output"]] = out
