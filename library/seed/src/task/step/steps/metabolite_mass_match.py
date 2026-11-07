"""Metabolite database mass matching."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._ms68_common import PROTON, column, row_labels, tabular


ADDUCTS = {"[M+H]+": (1, PROTON), "[M+Na]+": (1, 22.989218),
           "[M+NH4]+": (1, 18.033823), "[M-H]-": (-1, -PROTON),
           "[M+2H]2+": (2, 2 * PROTON)}


class MetaboliteMassMatchStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "metabolite_mass_match",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Metabolite mass match",
        "category": "Metabolomics",
        "icon": "Table",
        "description": "Match observed m/z values to a metabolite database within a ppm tolerance.",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"]},
                       {"logical_type": "form", "representations": ["form"]}],
            "outputs": [{"logical_type": "form", "representations": ["form"]}],
        },
        "contracts": {
            "version": 1,
            "inputs": [{"dims": [{"param": "feature_dim", "default": "feature"},
                                 {"param": "field_dim", "default": "field"}]},
                       {"dims": [{"param": "entry_dim", "default": "entry"},
                                 {"param": "database_field_dim", "default": "database_field"}]}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False,
                      "estimate": "estimate_memory"},
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
    }
    parameters_file = "metabolite_mass_match.MetaboliteMassMatchStep.parameters.json"

    def run(self, ctx, inputs):
        features, database = inputs
        field_dim = ctx.step_params.get("field_dim", "field")
        db_field = ctx.step_params.get("database_field_dim", "database_field")
        output = ctx.step_params.get("output", "matches")
        tolerance_ppm = float(ctx.step_params.get("tolerance_ppm", 10.0))
        mz = column(features, field_dim, "mz")
        names = row_labels(database, "entry")
        masses = column(database, db_field, "neutral_mass")
        rows = []
        for i, obs in enumerate(mz):
            best = None
            for j, name in enumerate(names):
                for adduct, (z, shift) in ADDUCTS.items():
                    theo = (masses[j] + shift) / abs(z)
                    ppm = (obs - theo) / theo * 1e6
                    if abs(ppm) <= tolerance_ppm and (best is None or abs(ppm) < abs(best[3])):
                        best = [i, j, adduct, ppm, theo]
            if best is not None:
                rows.append([best[0], best[1], best[3], best[4]])
        data = np.asarray(rows, dtype=float) if rows else np.zeros((0, 4))
        labels = {"feature": {str(int(r[0])): k for k, r in enumerate(data)},
                  "statistic": {"feature_index": 0, "entry_index": 1,
                                 "ppm_error": 2, "theoretical_mz": 3}}
        out = tabular(["feature", "statistic"], labels, data, "matches",
                      {"names": {str(int(r[0])): names[int(r[1])] for r in data}})
        ctx[output] = out

    def export(self, ctx):
        return {"format": "form"}
