"""b60 operator kraken_kreport_parse."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.step.base import Step
from ._b60_common import numeric, row_form


class KrakenKreportParseStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "kraken_kreport_parse",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Kraken kreport rank summary",
        "category": "Metagenomics",
        "description": "Kraken kreport rank summary.",
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
    parameters_file = "kraken_kreport_parse.KrakenKreportParseStep.parameters.json"

    def run(self, ctx, inputs):
        form = inputs[0]

        depth = numeric(form, "field", "depth", "kraken")
        rank = numeric(form, "field", "rank_code", "kraken")
        total = float(np.sum(depth))
        species = float(np.sum(depth[rank == 6]))
        genus = float(np.sum(depth[rank >= 5]))
        out = row_form(["total_reads", "species_fraction", "genus_fraction", "max_rank"],
                       [[total, species / total if total else 0.0,
                         genus / total if total else 0.0, float(np.max(rank))]],
                       "summary", {"all": 0})

        out.validate()
        ctx[ctx.step_params.get("output", "output")] = out

    def export(self, ctx):
        name = ctx.step_params.get("output", "output")
        f = ctx[name]
        return {"result_files": [], "output": name, "rows": int(f.data.shape[0]),
                 "columns": [str(x) for x in f.labels.get("statistic", [])]}
