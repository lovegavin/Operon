"""b75 causal-inference operator synthetic_control."""
import numpy as np

from src.core import Form
from src.task.step.base import Step
from src.task.step.steps.causal_b75_common import ols, result_form, _field, _has

class SyntheticControlStep(Step):

    definition = {
        "id": "synthetic_control",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Synthetic control ATT",
        "category": "Causal inference",
        "icon": "Table",
        "description": "Simplex-weighted donor pool fitted on pre-treatment periods, ATT on post periods.",
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

    parameters_file = "synthetic_control.SyntheticControlStep.parameters.json"

    def estimate_memory(self, inputs, params, profiles):
        return 64 * 1024 * 1024

    def run(self, ctx, inputs):
        p = ctx.step_params
        form = inputs[0]
        y = _field(form, "outcome"); unit = _field(form, "unit"); time = _field(form, "time"); treat = _field(form, "treatment")
        mask = np.isfinite(y) & np.isfinite(unit) & np.isfinite(time) & np.isfinite(treat)
        y, unit, time, treat = y[mask], unit[mask], time[mask], treat[mask]
        treated = np.unique(unit[treat > 0])
        if treated.size != 1:
            raise ValueError("synthetic_control: exactly one treated unit is required")
        treated = treated[0]
        donor_ids = [u for u in np.unique(unit) if u != treated]
        pre_end = float(p.get("pre_end", 0.0))
        pre = time <= pre_end
        post = time > pre_end
        Y = np.column_stack([y[(unit == u)] for u in donor_ids])
        times = np.array([time[unit == u][0] for u in donor_ids])
        order = np.argsort(times)
        Y = Y[:, order]
        yt = y[unit == treated]
        tt = time[unit == treated]
        tpre = tt <= pre_end
        tpost = tt > pre_end
        ypre = yt[tpre]
        Ypre = Y[time[unit == donor_ids[0]] <= pre_end]
        n = len(donor_ids)
        from scipy.optimize import minimize
        def loss(w):
            return float(np.mean((Ypre @ w - ypre) ** 2))
        w0 = np.ones(n) / n
        res = minimize(loss, w0, method="SLSQP", bounds=[(0, 1)] * n,
                       constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1.0}])
        w = np.clip(res.x, 0, None)
        w = w / w.sum()
        pre_rmse = float(np.sqrt(np.mean((Ypre @ w - ypre) ** 2)))
        Ypost = Y[time[unit == donor_ids[0]] > pre_end]
        att = float(np.mean(yt[tpost] - Ypost @ w))
        out = result_form(["att", "pre_rmse", "n_donors", "n_pre", "n_post"],
                          [att, pre_rmse, n, int(tpre.sum()), int(tpost.sum())])
        ctx[str(p.get("output") or "output")] = out

