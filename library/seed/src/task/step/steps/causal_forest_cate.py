"""Causal forest operators backed by econml (b92)."""

from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._b92_common import column, design, matrix, row_names, table


class CausalForestCateStep(Step):
    parameters_file = "causal_forest_cate.CausalForestCateStep.parameters.json"
    definition = {'id': 'causal_forest_cate', 'version': '1.0.0', 'title': 'Causal forest conditional effects', 'description': 'Per-sample conditional average treatment effects with 95% confidence intervals.', 'category': 'Causal inference', 'icon': 'users', 'protocol_version': 3, 'protocol_revision': '3.7', 'kind': 'operator', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    def run(self, ctx, inputs):
        y_column = ctx.step_params["y_column"]
        t_column = ctx.step_params["t_column"]
        n_estimators = ctx.step_params["n_estimators"]
        min_samples_leaf = ctx.step_params["min_samples_leaf"]
        seed = ctx.step_params["seed"]
        x, names = design(inputs[0], {y_column, t_column})
        y = column(inputs[0], y_column)
        t = column(inputs[0], t_column)
        if x.shape[0] < 8:
            raise ValueError("need at least 8 samples")
        from econml.dml import CausalForestDML
        from sklearn.linear_model import LinearRegression, LogisticRegression

        est = CausalForestDML(
            model_y=LinearRegression(),
            model_t=LogisticRegression(max_iter=500),
            discrete_treatment=True,
            n_estimators=int(n_estimators),
            min_samples_leaf=int(min_samples_leaf),
            random_state=int(seed),
            cv=2,
        )
        est.fit(y, t, X=x)
        eff = np.asarray(est.effect(x), dtype=float)
        lo, hi = est.effect_interval(x, alpha=0.05)
        values = {
            "effect": eff,
            "ci_low": np.asarray(lo, dtype=float),
            "ci_high": np.asarray(hi, dtype=float),
        }
        out = table(["sample"], values, ["effect", "ci_low", "ci_high"])
        out.dims[0] = "sample"
        out.labels["sample"] = {name: i for i, name in enumerate(row_names(inputs[0]))}

        ctx[ctx.step_params["output"]] = out
