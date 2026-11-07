"""b75 causal-inference operator doubly_robust_ate."""
import numpy as np

from src.core import Form
from src.task.step.base import Step
from src.task.step.steps.causal_b75_common import ols, result_form, _field, _has

class DoublyRobustAteStep(Step):

    definition = {
        "id": "doubly_robust_ate",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Doubly robust ATE (AIPW)",
        "category": "Causal inference",
        "icon": "Table",
        "description": "AIPW average treatment effect with logistic propensity and linear outcome models.",
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

    parameters_file = "doubly_robust_ate.DoublyRobustAteStep.parameters.json"

    def estimate_memory(self, inputs, params, profiles):
        return 64 * 1024 * 1024

    def run(self, ctx, inputs):
        p = ctx.step_params
        form = inputs[0]
        y = _field(form, "outcome"); t = _field(form, "treatment")
        cov = [c for c in ("x1", "x2") if _has(form, c)]
        X = np.column_stack([np.ones_like(y)] + [_field(form, c) for c in cov])
        mask = np.isfinite(y) & np.isfinite(t) & np.all(np.isfinite(X), axis=1)
        y, t, X = y[mask], t[mask], X[mask]
        from sklearn.linear_model import LogisticRegression, LinearRegression
        ps = LogisticRegression(max_iter=1000, solver="lbfgs").fit(X[:, 1:], t).predict_proba(X[:, 1:])[:, 1]
        ps = np.clip(ps, 1e-6, 1 - 1e-6)
        m1 = LinearRegression().fit(X[t == 1], y[t == 1]).predict(X)
        m0 = LinearRegression().fit(X[t == 0], y[t == 0]).predict(X)
        score = t * (y - m1) / ps + m1 - (1 - t) * (y - m0) / (1 - ps) - m0
        ate = float(score.mean())
        se = float(score.std(ddof=1) / np.sqrt(score.size))
        out = result_form(["ate", "std_error", "ci_low", "ci_high", "n_treated", "n_control"],
                          [ate, se, ate - 1.96 * se, ate + 1.96 * se, int(t.sum()), int((1 - t).sum())])
        ctx[str(p.get("output") or "output")] = out

