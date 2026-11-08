"""Propensity-score ATT matching (b94)."""

from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._b94_common import column, controls, matrix, row_names, table


class PropensityScoreMatchingStep(Step):
    parameters_file = "propensity_score_matching.PropensityScoreMatchingStep.parameters.json"
    definition = {'id': 'propensity_score_matching', 'version': '1.0.0', 'title': 'Propensity-score ATT matching', 'description': 'Logistic propensity scores with one-to-one nearest-neighbour ATT matching.', 'category': 'Causal inference', 'icon': 'causal', 'protocol_version': 3, 'protocol_revision': '3.7', 'kind': 'operator', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    def run(self, ctx, inputs):
        t = column(inputs[0], ctx.step_params["treatment_column"])
        y = column(inputs[0], ctx.step_params["outcome_column"])
        cov, names = controls(inputs[0], ctx.step_params["covariate_columns"])
        X = np.column_stack(cov)
        if X.shape[0] < 4 or X.shape[1] < 1:
            raise ValueError("need at least one covariate and four samples")
        mu = X.mean(axis=0)
        sd = X.std(axis=0)
        sd[sd == 0] = 1.0
        Xs = (X - mu) / sd
        Xd = np.column_stack([np.ones(X.shape[0]), Xs])
        beta = np.zeros(Xd.shape[1])
        for _ in range(100):
            eta = np.clip(Xd @ beta, -30, 30)
            pr = 1.0 / (1.0 + np.exp(-eta))
            W = pr * (1.0 - pr) + 1e-9
            z = eta + (t - pr) / W
            beta_new = np.linalg.solve(Xd.T @ (Xd * W[:, None]), Xd.T @ (W * z))
            if np.max(np.abs(beta_new - beta)) < 1e-10:
                beta = beta_new
                break
            beta = beta_new
        ps = 1.0 / (1.0 + np.exp(-np.clip(Xd @ beta, -30, 30)))
        cal = float(ctx.step_params.get("caliper", 0.1))
        treated = np.where(t > 0.5)[0]
        control = np.where(t <= 0.5)[0]
        diffs = []
        for i in treated:
            d = np.abs(ps[control] - ps[i])
            j = int(np.argmin(d))
            if d[j] <= cal:
                diffs.append(float(y[i] - y[control[j]]))
        if not diffs:
            raise ValueError("no treated unit matched within the caliper")
        diffs = np.asarray(diffs)
        att = float(diffs.mean())
        se = float(diffs.std(ddof=1) / np.sqrt(diffs.size)) if diffs.size > 1 else 0.0
        tstat = att / se if se > 0 else 0.0
        from scipy import stats as st
        p = float(2.0 * st.t.sf(abs(tstat), max(diffs.size - 1, 1)))
        vals = {"att": [att], "stderr": [se], "t": [tstat], "p": [p],
                "n_treated": [float(treated.size)], "n_matched": [float(diffs.size)]}
        out = table("stat", vals, ["att", "stderr", "t", "p", "n_treated", "n_matched"])
        ctx[ctx.step_params["output"]] = out
