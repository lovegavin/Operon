"""Definition for the mlst_typing operator."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.step.base import Step
from ._b59_common import numeric, strings, row_form


class MlstTypingStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "mlst_typing",
        "version": "1.0.0",
        "kind": "operator",
        "title": "MLST sequence type assignment",
        "category": "Metagenomics",
        "description": "MLST sequence type assignment.",
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
    parameters_file = "mlst_typing.MlstTypingStep.parameters.json"

    def run(self, ctx, inputs):

        form = inputs[0]
        loci = int(ctx.step_params.get("loci", 7))
        cols = [numeric(form, "field", f"locus{i+1}", "mlst") for i in range(loci)]
        st = {}
        rows = []
        for i in range(form.data.shape[0]):
            key = tuple(int(c[i]) for c in cols)
            code = st.setdefault(key, len(st) + 1)
            rows.append([code, len(key)])
        lab = dict((form.labels or {}).get("isolate") or {}) or {f"i{i}": i for i in range(len(rows))}
        out = row_form(["st_code", "n_loci"], rows, "isolate", lab,
                       info={"n_sequence_types": len(st)})

        out.validate()
        ctx[ctx.step_params.get("output", "output")] = out

    def export(self, ctx):
        name = ctx.step_params.get("output", "output")
        f = ctx[name]
        return {"result_files": [], "output": name, "dims": [str(d) for d in f.dims],
                 "rows": int(f.data.shape[0]), "columns": [str(x) for x in f.labels.get("statistic", [])]}
