"""b60 operator plasmid_contig_filter."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.step.base import Step
from ._b60_common import numeric, row_form


class PlasmidContigFilterStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "plasmid_contig_filter",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Plasmid-like contig filter",
        "category": "Metagenomics",
        "description": "Plasmid-like contig filter.",
        "inputs_arity": 1,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "numeric": False, "ndim": 2,
                        "dims": [{"param": "row_dim", "default": "contig"},
                                 {"param": "field_dim", "default": "field"}]}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "data_formats": {"inputs": [{"logical_type": "form", "representations": ["form"]}],
                          "outputs": [{"logical_type": "form", "representations": ["form"]}]},
    }
    parameters_file = "plasmid_contig_filter.PlasmidContigFilterStep.parameters.json"

    def run(self, ctx, inputs):
        form = inputs[0]

        length = numeric(form, "field", "length", "plasmid")
        depth = numeric(form, "field", "depth", "plasmid")
        circular = numeric(form, "field", "circular", "plasmid")
        ml = float(ctx.step_params.get("min_length", 1000))
        md = float(ctx.step_params.get("min_depth", 5.0))
        ok = (length >= ml) & (depth >= md)
        rows = [[l, d, c, 1.0 if p else 0.0] for l, d, c, p in zip(length, depth, circular, ok)]
        out = row_form(["length", "depth", "circular", "pass"], rows, "contig",
                       {f"c{i}": i for i in range(len(rows))},
                       info={"n_pass": int(np.sum(ok)), "bp_pass": float(np.sum(length[ok]))})

        out.validate()
        ctx[ctx.step_params.get("output", "output")] = out

    def export(self, ctx):
        name = ctx.step_params.get("output", "output")
        f = ctx[name]
        return {"result_files": [], "output": name, "rows": int(f.data.shape[0]),
                 "columns": [str(x) for x in f.labels.get("statistic", [])]}
