"""b60 operator metaphlan_profile_parse."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.step.base import Step
from ._b60_common import numeric, row_form


class MetaphlanProfileParseStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "metaphlan_profile_parse",
        "version": "1.0.0",
        "kind": "operator",
        "title": "MetaPhlAn rank profile summary",
        "category": "Metagenomics",
        "description": "MetaPhlAn rank profile summary.",
        "inputs_arity": 1,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "numeric": False, "ndim": 2,
                        "dims": [{"param": "row_dim", "default": "taxon"},
                                 {"param": "field_dim", "default": "field"}]}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "data_formats": {"inputs": [{"logical_type": "form", "representations": ["form"]}],
                          "outputs": [{"logical_type": "form", "representations": ["form"]}]},
    }
    parameters_file = "metaphlan_profile_parse.MetaphlanProfileParseStep.parameters.json"

    def run(self, ctx, inputs):
        form = inputs[0]

        rel = numeric(form, "field", "relative_abundance", "metaphlan")
        rank = numeric(form, "field", "rank_code", "metaphlan")
        if np.any(rel < 0):
            raise StepError("metaphlan: relative_abundance must be non-negative")
        rows = []
        for r in range(7):
            vals = rel[rank == r]
            s = float(np.sum(vals))
            rows.append([s, float(vals.size), s / max(1e-12, float(np.sum(rel)))])
        nz = rel[rel > 0]
        shannon = float(-np.sum(nz * np.log(nz))) if nz.size else 0.0
        out = row_form(["rank_sum", "n_taxa", "rank_fraction"], rows,
                       "rank", {str(i): i for i in range(7)},
                       info={"shannon": shannon, "total": float(np.sum(rel))})

        out.validate()
        ctx[ctx.step_params.get("output", "output")] = out

    def export(self, ctx):
        name = ctx.step_params.get("output", "output")
        f = ctx[name]
        return {"result_files": [], "output": name, "rows": int(f.data.shape[0]),
                 "columns": [str(x) for x in f.labels.get("statistic", [])]}
