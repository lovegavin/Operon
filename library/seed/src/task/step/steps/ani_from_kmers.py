"""Definition for the ani_from_kmers operator."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.step.base import Step
from ._b59_common import numeric, strings, row_form


class AniFromKmersStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "ani_from_kmers",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ANI from shared k-mer counts",
        "category": "Metagenomics",
        "description": "ANI from shared k-mer counts.",
        "inputs_arity": 1,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "dims": [{"param": "row_dim", "default": "kmer"}, {"param": "field_dim", "default": "field"}], "numeric": False, "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "data_formats": {"inputs": [{"logical_type": "form", "representations": ["form"]}], "outputs": [{"logical_type": "form", "representations": ["form"]}]},
    }
    parameters_file = "ani_from_kmers.AniFromKmersStep.parameters.json"

    def run(self, ctx, inputs):

        form = inputs[0]
        a = numeric(form, "field", "count_a", "ani_from_kmers")
        b = numeric(form, "field", "count_b", "ani_from_kmers")
        k = int(ctx.step_params.get("k", 21))
        pa, pb = a > 0, b > 0
        shared = int(np.sum(pa & pb)); union = int(np.sum(pa | pb))
        jac = shared / union if union else 0.0
        dist = 1.0 if jac <= 0 else -(1.0 / k) * np.log(2.0 * jac / (1.0 + jac))
        ani = max(0.0, min(1.0, 1.0 - dist))
        out = row_form(["shared_kmers", "union_kmers", "jaccard", "mash_distance", "ani"],
                       [[shared, union, jac, dist, ani]], "genome_pair", {"pair": 0})

        out.validate()
        ctx[ctx.step_params.get("output", "output")] = out

    def export(self, ctx):
        name = ctx.step_params.get("output", "output")
        f = ctx[name]
        return {"result_files": [], "output": name, "dims": [str(d) for d in f.dims],
                 "rows": int(f.data.shape[0]), "columns": [str(x) for x in f.labels.get("statistic", [])]}
