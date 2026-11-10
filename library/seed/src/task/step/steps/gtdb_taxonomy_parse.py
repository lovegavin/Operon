"""Definition for the gtdb_taxonomy_parse operator."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.step.base import Step
from ._b59_common import numeric, strings, row_form


class GtdbTaxonomyParseStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "gtdb_taxonomy_parse",
        "version": "1.0.0",
        "kind": "operator",
        "title": "GTDB taxonomy rank completeness",
        "category": "Metagenomics",
        "description": "GTDB taxonomy rank completeness.",
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
    parameters_file = "gtdb_taxonomy_parse.GtdbTaxonomyParseStep.parameters.json"

    def run(self, ctx, inputs):

        form = inputs[0]
        taxa = strings(form, "field", "taxonomy", "gtdb_taxonomy")
        ranks = ["d", "p", "c", "o", "f", "g", "s"]
        counts = {r: 0 for r in ranks}
        for t in taxa:
            for part in str(t).split(";"):
                part = part.strip()
                if len(part) >= 3 and part[0] in counts and part[1] == "_" and part[2] == "_":
                    if part[3:].strip():
                        counts[part[0]] += 1
        n = max(1, len(taxa))
        rows = [[counts[r], n - counts[r], 1.0 - counts[r] / n] for r in ranks]
        out = row_form(["classified", "unclassified", "unclassified_fraction"], rows,
                       "rank", {r: i for i, r in enumerate(ranks)})

        out.validate()
        ctx[ctx.step_params.get("output", "output")] = out

    def export(self, ctx):
        name = ctx.step_params.get("output", "output")
        f = ctx[name]
        return {"result_files": [], "output": name, "dims": [str(d) for d in f.dims],
                 "rows": int(f.data.shape[0]), "columns": [str(x) for x in f.labels.get("statistic", [])]}
