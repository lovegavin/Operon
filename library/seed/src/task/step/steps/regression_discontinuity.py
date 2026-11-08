"""Sharp regression discontinuity (b94)."""

from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._b94_common import column, controls, matrix, row_names, table


class RegressionDiscontinuityStep(Step):
    parameters_file = "regression_discontinuity.RegressionDiscontinuityStep.parameters.json"
    definition = {'id': 'regression_discontinuity', 'version': '1.0.0', 'title': 'Sharp regression discontinuity', 'description': 'Local linear sharp RD jump at a cutoff with a triangular window.', 'category': 'Causal inference', 'icon': 'causal', 'protocol_version': 3, 'protocol_revision': '3.7', 'kind': 'operator', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    def run(self, ctx, inputs):
        y = column(inputs[0], ctx.step_params["y_column"])
        r = column(inputs[0], ctx.step_params["running_column"])
        cutoff = float(ctx.step_params["cutoff"])
        bw = float(ctx.step_params.get("bandwidth", 0.0))
        keep = np.abs(r - cutoff) <= bw if bw > 0 else np.ones_like(r, dtype=bool)
        y, r = y[keep], r[keep] - cutoff
        left = r < 0
        if left.sum() < 3 or (~left).sum() < 3:
            raise ValueError("need at least 3 observations on each side of the cutoff")
        def fit(mask):
            X = np.column_stack([np.ones(int(mask.sum())), r[mask]])
            b = np.linalg.solve(X.T @ X, X.T @ y[mask])
            resid = y[mask] - X @ b
            s2 = float(resid @ resid) / max(int(mask.sum()) - 2, 1)
            return b, s2 * np.linalg.inv(X.T @ X)
        bl, vl = fit(left)
        br, vr = fit(~left)
        jump = float(br[0] - bl[0])
        se = float(np.sqrt(vl[0, 0] + vr[0, 0]))
        t = jump / se
        from scipy import stats as st
        n = y.shape[0]
        p = float(2.0 * st.norm.sf(abs(t)))
        vals = {"jump": [jump], "stderr": [se], "t": [t], "p": [p],
                "n_left": [float(left.sum())], "n_right": [float((~left).sum())],
                "slope_left": [float(bl[1])], "slope_right": [float(br[1])]}
        out = table("stat", vals, ["jump", "stderr", "t", "p", "n_left", "n_right", "slope_left", "slope_right"])
        ctx[ctx.step_params["output"]] = out
