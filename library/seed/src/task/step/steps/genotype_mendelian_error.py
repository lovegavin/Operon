"""Definition for the genotype_mendelian_error operator."""
import numpy as np
from src.core import StepError
from src.task.step.base import Step
from ._genotype_common import form, index, labels

class GenotypeMendelianErrorStep(Step):
    definition = {
        "protocol_version": 3, "protocol_revision": "3.7", "id": "genotype_mendelian_error",
        "version": "1.0.0", "kind": "operator", "title": "Trio Mendelian error scan",
        "category": "Population genetics", "description": "Counts child genotypes incompatible with both parents.",
        "inputs_arity": 1, "output_parameter": "output", "outputs": [],
        "contracts": {"version": 1,
            "inputs": [{"version": 1, "dims": [{"param": "variant_dim", "default": "variant"}, {"param": "sample_dim", "default": "sample"}], "numeric": True, "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}},
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "data_formats": {"inputs": [{"logical_type": "form", "representations": ["form"]}],
                         "outputs": [{"logical_type": "form", "representations": ["form"]}]},
    }
    parameters_file = "genotype_mendelian_error.GenotypeMendelianErrorStep.parameters.json"

    def run(self, ctx, inputs):
        form_in = inputs[0]
        M = np.asarray(form_in.data, dtype=float)
        f = index(form_in, ctx.step_params.get("father_label", "father"))
        m = index(form_in, ctx.step_params.get("mother_label", "mother"))
        c = index(form_in, ctx.step_params.get("child_label", "child"))
        err, ntest, fd, md, cd = [], 0, [], [], []
        for i in range(M.shape[0]):
            fv, mv, cv = M[i, f], M[i, m], M[i, c]
            fd.append(fv); md.append(mv); cd.append(cv)
            if not (np.isfinite(fv) and np.isfinite(mv) and np.isfinite(cv)):
                err.append(0.0); continue
            fv, mv, cv = int(fv), int(mv), int(cv)
            poss = {a + b for a in range(2) for b in range(2)
                    if a <= fv and b <= mv and fv - a <= 1 and mv - b <= 1}
            err.append(0.0 if cv in poss else 1.0); ntest += 1
        vdim = str(form_in.dims[0])
        out = form(["mendelian_error", "father_dosage", "mother_dosage", "child_dosage"],
                   [err, fd, md, cd], vdim, form_in.labels.get(vdim, {}))
        out.info.update({"n_tested": ntest, "n_errors": int(sum(err))})
        out.validate()
        ctx[ctx.step_params.get("output", "output")] = out

    def export(self, ctx):
        name = ctx.step_params.get("output", "output")
        f = ctx[name]
        return {"result_files": [], "output": name, "dims": [str(d) for d in f.dims],
                "rows": int(f.data.shape[0]), "columns": [str(x) for x in f.labels.get("statistic", [])]}
