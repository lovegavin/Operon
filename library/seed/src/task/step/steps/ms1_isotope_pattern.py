"""Observed isotope envelope scoring."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._ms68_common import ELEMENTS, PROTON, column, tabular
from ._formula_common import parse_formula


class Ms1IsotopePatternStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "ms1_isotope_pattern",
        "version": "1.0.0",
        "kind": "operator",
        "title": "MS1 isotope pattern",
        "category": "Metabolomics",
        "icon": "Chart",
        "description": "Compare an observed isotope envelope with a theoretical formula distribution.",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"]}],
            "outputs": [{"logical_type": "form", "representations": ["form"]}],
        },
        "contracts": {
            "version": 1,
            "inputs": [{"dims": [{"param": "peak_dim", "default": "peak"},
                                 {"param": "field_dim", "default": "field"}]}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False,
                      "estimate": "estimate_memory"},
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }
    parameters_file = "ms1_isotope_pattern.Ms1IsotopePatternStep.parameters.json"

    def run(self, ctx, inputs):
        form = inputs[0]
        field_dim = ctx.step_params.get("field_dim", "field")
        output = ctx.step_params.get("output", "isotopes")
        formula = str(ctx.step_params.get("formula", "C6H12O6"))
        charge = int(ctx.step_params.get("charge", 1))
        tolerance_ppm = float(ctx.step_params.get("tolerance_ppm", 20.0))
        counts = parse_formula(formula)
        dist = [(0.0, 1.0)]
        for element, n in counts.items():
            options = ELEMENTS.get(element)
            if not options:
                continue
            for _ in range(n):
                nxt = {}
                for mass, prob in dist:
                    for dm, dp in options:
                        key = round((mass + dm) * 1e6) / 1e6
                        nxt[key] = nxt.get(key, 0.0) + prob * dp
                dist = sorted(nxt.items())[:8]
                total = sum(p for _, p in dist)
                dist = [(m, p / total) for m, p in dist]
        theo_mz = np.asarray([(m + charge * PROTON) / charge for m, _ in dist])
        theo_rel = np.asarray([p for _, p in dist])
        theo_rel = theo_rel / theo_rel.max()
        mz = column(form, field_dim, "mz")
        intensity = column(form, field_dim, "intensity")
        rows = []
        for tmz, trel in zip(theo_mz, theo_rel):
            ppm = (mz - tmz) / tmz * 1e6
            hit = int(np.argmin(np.abs(ppm)))
            if abs(ppm[hit]) > tolerance_ppm:
                rows.append([tmz, trel, 0.0, np.nan, abs(ppm[hit])])
            else:
                rows.append([tmz, trel, intensity[hit] / intensity.max(), ppm[hit], abs(ppm[hit])])
        data = np.asarray(rows, dtype=float)
        labels = {"isotope": {str(i): i for i in range(data.shape[0])},
                  "statistic": {"theoretical_mz": 0, "theoretical_relative": 1,
                                "observed_relative": 2, "ppm_error": 3, "abs_ppm": 4}}
        out = tabular(["isotope", "statistic"], labels, data, "isotope",
                      {"formula": formula, "charge": charge})
        ctx[output] = out

    def export(self, ctx):
        return {"format": "form"}
