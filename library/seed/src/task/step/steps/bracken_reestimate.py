"""b60 operator bracken_reestimate."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.step.base import Step
from ._b60_common import numeric, row_form


class BrackenReestimateStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "bracken_reestimate",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Bracken genome-length abundance",
        "category": "Metagenomics",
        "description": "Bracken genome-length abundance.",
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
    parameters_file = "bracken_reestimate.BrackenReestimateStep.parameters.json"

    def run(self, ctx, inputs):
        form = inputs[0]

        reads = numeric(form, "field", "reads", "bracken")
        length = numeric(form, "field", "genome_length", "bracken")
        if np.any(length <= 0):
            raise StepError("bracken: genome_length must be positive")
        abundance = reads / length
        total = float(np.sum(abundance))
        rel = abundance / total if total else abundance
        rows = [[a, r, r * 1e6] for a, r in zip(abundance, rel)]
        n = len(rows)
        out = row_form(["abundance", "relative_abundance", "per_million"],
                       rows, "taxon", {f"t{i}": i for i in range(n)},
                       info={"total_abundance": total})

        out.validate()
        ctx[ctx.step_params.get("output", "output")] = out

    def export(self, ctx):
        name = ctx.step_params.get("output", "output")
        f = ctx[name]
        return {"result_files": [], "output": name, "rows": int(f.data.shape[0]),
                 "columns": [str(x) for x in f.labels.get("statistic", [])]}
