"""b60 operator humann_pathway_abundance."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.step.base import Step
from ._b60_common import numeric, row_form


class HumannPathwayAbundanceStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "humann_pathway_abundance",
        "version": "1.0.0",
        "kind": "operator",
        "title": "HUMAnN pathway abundance summary",
        "category": "Metagenomics",
        "description": "HUMAnN pathway abundance summary.",
        "inputs_arity": 1,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "numeric": False, "ndim": 2,
                        "dims": [{"param": "row_dim", "default": "pathway"},
                                 {"param": "field_dim", "default": "field"}]}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "data_formats": {"inputs": [{"logical_type": "form", "representations": ["form"]}],
                          "outputs": [{"logical_type": "form", "representations": ["form"]}]},
    }
    parameters_file = "humann_pathway_abundance.HumannPathwayAbundanceStep.parameters.json"

    def run(self, ctx, inputs):
        form = inputs[0]

        v = numeric(form, "field", "abundance", "humann")
        if np.any(v < 0):
            raise StepError("humann: abundance must be non-negative")
        total = float(np.sum(v))
        p = v / total if total else v
        nz = p[p > 0]
        shannon = float(-np.sum(nz * np.log(nz))) if nz.size else 0.0
        rows = [[total, float(np.mean(v)), float(np.median(v)), shannon,
                 float(np.max(p)) if p.size else 0.0]]
        out = row_form(["total_abundance", "mean", "median", "shannon", "top_fraction"],
                       rows, "summary", {"all": 0})

        out.validate()
        ctx[ctx.step_params.get("output", "output")] = out

    def export(self, ctx):
        name = ctx.step_params.get("output", "output")
        f = ctx[name]
        return {"result_files": [], "output": name, "rows": int(f.data.shape[0]),
                 "columns": [str(x) for x in f.labels.get("statistic", [])]}
