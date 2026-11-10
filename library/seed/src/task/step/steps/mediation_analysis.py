"""b75 causal-inference operator mediation_analysis."""
import numpy as np

from src.core import Form
from src.task.step.base import Step
from src.task.step.steps.causal_b75_common import ols, result_form, _field, _has

class MediationAnalysisStep(Step):

    definition = {
        "id": "mediation_analysis",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Mediation analysis",
        "category": "Causal inference",
        "icon": "Table",
        "description": "Product-of-coefficients mediation with delta-method inference.",
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

    parameters_file = "mediation_analysis.MediationAnalysisStep.parameters.json"

    def estimate_memory(self, inputs, params, profiles):
        return 64 * 1024 * 1024

    def run(self, ctx, inputs):
        p = ctx.step_params
        form = inputs[0]
        y = _field(form, "outcome"); t = _field(form, "treatment"); m = _field(form, "mediator")
        mask = np.isfinite(y) & np.isfinite(t) & np.isfinite(m)
        y, t, m = y[mask], t[mask], m[mask]
        Xm = np.column_stack([np.ones_like(t), t])
        bm, sm, tm, pm, _ = ols(Xm, m)
        Xy = np.column_stack([np.ones_like(t), t, m])
        by, sy, ty, py, _ = ols(Xy, y)
        a, b = bm[1], by[2]
        acme = a * b
        se_acme = float(np.sqrt(b ** 2 * sm[1] ** 2 + a ** 2 * sy[2] ** 2))
        total = by[1] + acme
        prop = acme / total if abs(total) > 0 else np.nan
        z = acme / se_acme if se_acme > 0 else np.nan
        pval = 2.0 * __import__("scipy").stats.norm.sf(abs(z))
        out = result_form(["acme", "direct", "total", "prop_mediated", "acme_se", "z", "p_value"],
                          [acme, by[1], total, prop, se_acme, z, pval])
        ctx[str(p.get("output") or "output")] = out

