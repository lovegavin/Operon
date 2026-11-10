"""Definition for the checkm_quality_parse operator."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.step.base import Step
from ._b59_common import numeric, strings, row_form


class CheckmQualityParseStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "checkm_quality_parse",
        "version": "1.0.0",
        "kind": "operator",
        "title": "CheckM/CheckM2 genome quality score",
        "category": "Metagenomics",
        "description": "CheckM/CheckM2 genome quality score.",
        "inputs_arity": 1,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "dims": [{"param": "row_dim", "default": "row"}, {"param": "field_dim", "default": "field"}], "numeric": False, "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "data_formats": {"inputs": [{"logical_type": "form", "representations": ["form"]}], "outputs": [{"logical_type": "form", "representations": ["form"]}]},
    }
    parameters_file = "checkm_quality_parse.CheckmQualityParseStep.parameters.json"

    def run(self, ctx, inputs):

        form = inputs[0]
        comp = numeric(form, "field", "completeness", "checkm")
        cont = numeric(form, "field", "contamination", "checkm")
        q = comp - 5.0 * cont
        rows = [[c, t, v] for c, t, v in zip(comp, cont, q)]
        lab = dict((form.labels or {}).get("genome") or {}) or {f"g{i}": i for i in range(len(rows))}
        out = row_form(["completeness", "contamination", "quality_score"], rows, "genome", lab)

        out.validate()
        ctx[ctx.step_params.get("output", "output")] = out

    def export(self, ctx):
        name = ctx.step_params.get("output", "output")
        f = ctx[name]
        return {"result_files": [], "output": name, "dims": [str(d) for d in f.dims],
                 "rows": int(f.data.shape[0]), "columns": [str(x) for x in f.labels.get("statistic", [])]}
