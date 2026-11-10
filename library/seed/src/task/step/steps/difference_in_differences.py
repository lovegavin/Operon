"""b75 causal-inference operator difference_in_differences."""
import numpy as np

from src.core import Form
from src.task.step.base import Step
from src.task.step.steps.causal_b75_common import ols, result_form, _field, _has

class DifferenceInDifferencesStep(Step):

    definition = {
        "id": "difference_in_differences",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Difference-in-differences estimate",
        "category": "Causal inference",
        "icon": "Table",
        "description": "Two-way fixed-effect style DiD from outcome, treatment and post columns with HC1 inference.",
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
        "contracts": {
            "version": 1,
            "inputs": [{"dims": [{"param": "row_dim", "default": "row"},
                                  {"param": "field_dim", "default": "field"}],
                        "labels": [], "parallel": [], "numeric": True, "ndim": 2}],
            "output": {"mode": "declare",
                        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    parameters_file = "difference_in_differences.DifferenceInDifferencesStep.parameters.json"

    def estimate_memory(self, inputs, params, profiles):
        return 64 * 1024 * 1024

    def run(self, ctx, inputs):
        p = ctx.step_params
        form = inputs[0]
        y = _field(form, "outcome"); t = _field(form, "treatment"); post = _field(form, "post")
        mask = np.isfinite(y) & np.isfinite(t) & np.isfinite(post)
        y, t, post = y[mask], t[mask], post[mask]
        X = np.column_stack([np.ones_like(y), t, post, t * post])
        beta, se, tv, pv, r2 = ols(X, y)
        out = result_form(["estimate", "std_error", "t_stat", "p_value", "r2", "n_obs"],
                          [beta[3], se[3], tv[3], pv[3], r2, y.size])
        ctx[str(p.get("output") or "output")] = out

