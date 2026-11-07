"""Definition for the genotype_call_rate_qc operator."""
import numpy as np
from src.core import StepError
from src.task.step.base import Step
from ._genotype_common import form, index, labels

class GenotypeCallRateQcStep(Step):
    definition = {
        "protocol_version": 3, "protocol_revision": "3.7", "id": "genotype_call_rate_qc",
        "version": "1.0.0", "kind": "operator", "title": "Per-sample genotype call rate",
        "category": "Population genetics", "description": "Reports called fraction and a pass flag per sample.",
        "inputs_arity": 1, "output_parameter": "output", "outputs": [],
        "contracts": {"version": 1,
            "inputs": [{"version": 1, "dims": [{"param": "variant_dim", "default": "variant"}, {"param": "sample_dim", "default": "sample"}], "numeric": True, "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}},
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "data_formats": {"inputs": [{"logical_type": "form", "representations": ["form"]}],
                         "outputs": [{"logical_type": "form", "representations": ["form"]}]},
    }
    parameters_file = "genotype_call_rate_qc.GenotypeCallRateQcStep.parameters.json"

    def run(self, ctx, inputs):
        form_in = inputs[0]
        M = np.asarray(form_in.data, dtype=float)
        lab = labels(form_in)
        names = [None] * len(lab)
        for k, v in lab.items():
            names[int(v)] = str(k)
        total = M.shape[0]
        called = np.isfinite(M).sum(axis=0)
        rate = np.round(called / total if total else np.zeros(M.shape[1]), 8)
        flag = (rate >= float(ctx.step_params.get("min_call_rate", 0.9))).astype(float)
        out = form(["n_variants", "n_called", "call_rate", "missing_count", "pass_flag"],
                   [np.full(M.shape[1], total), called, rate, total - called, flag], "sample", names)
        out.validate()
        ctx[ctx.step_params.get("output", "output")] = out

    def export(self, ctx):
        name = ctx.step_params.get("output", "output")
        f = ctx[name]
        return {"result_files": [], "output": name, "dims": [str(d) for d in f.dims],
                "rows": int(f.data.shape[0]), "columns": [str(x) for x in f.labels.get("statistic", [])]}
