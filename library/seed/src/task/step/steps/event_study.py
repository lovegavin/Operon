"""b75 causal-inference operator event_study."""
import numpy as np

from src.core import Form
from src.task.step.base import Step
from src.task.step.steps.causal_b75_common import ols, result_form, _field, _has

class EventStudyStep(Step):

    definition = {
        "id": "event_study",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Event-study coefficients",
        "category": "Causal inference",
        "icon": "Table",
        "description": "Two-way within-transformed event-study regression on a balanced panel.",
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

    parameters_file = "event_study.EventStudyStep.parameters.json"

    def estimate_memory(self, inputs, params, profiles):
        return 64 * 1024 * 1024

    def run(self, ctx, inputs):
        p = ctx.step_params
        form = inputs[0]
        y = _field(form, "outcome"); unit = _field(form, "unit"); time = _field(form, "time"); treat = _field(form, "treatment")
        mask = np.isfinite(y) & np.isfinite(unit) & np.isfinite(time) & np.isfinite(treat)
        y, unit, time, treat = y[mask], unit[mask], time[mask], treat[mask]
        units = np.unique(unit); times = np.unique(time)
        rows = []
        for u in units:
            if np.any(treat[unit == u] > 0):
                rows.append(u)
        lo, hi = int(p.get("min_period", -5)), int(p.get("max_period", 5))
        # first treated period per unit
        first = {}
        for u in units:
            idx = np.where((unit == u) & (treat > 0))[0]
            first[u] = float(time[idx].min()) if idx.size else np.inf
        if not any(np.isfinite(v) for v in first.values()):
            raise ValueError("event_study: no treated observations")
        # two-way within transform
        yd = y.copy()
        for _ in range(1):
            for u in np.unique(unit):
                m = unit == u
                yd[m] -= yd[m].mean()
            for t in np.unique(time):
                m = time == t
                yd[m] -= yd[m].mean()
        rel = np.array([time[i] - first[unit[i]] if np.isfinite(first[unit[i]]) else -999 for i in range(y.size)])
        cols, names = [np.ones_like(yd)], ["const"]
        for k in range(lo, hi + 1):
            if k == -1:
                continue
            cols.append((rel == k).astype(float))
            names.append(f"event_{k}")
        X = np.column_stack(cols)
        Xd = X.copy()
        for _ in range(1):
            for u in units:
                m = unit == u
                Xd[m] -= Xd[m].mean(axis=0)
            for t in times:
                m = time == t
                Xd[m] -= Xd[m].mean(axis=0)
        beta, se, tv, pv, r2 = ols(Xd[:, 1:], yd)
        values, fields = [], []
        for j, name in enumerate(names[1:]):
            values.extend([beta[j], se[j], tv[j], pv[j]])
            fields.extend([f"{name}_coef", f"{name}_se", f"{name}_t", f"{name}_p"])
        out = result_form(fields + ["n_obs", "r2"], values + [y.size, r2])
        ctx[str(p.get("output") or "output")] = out

