"""Definition for the genomic_selection_rrblup operator."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step

from ._popgen_common import column, result_form, string_column


class GenomicSelectionRrblupStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "genomic_selection_rrblup",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Genomic selection (rrBLUP)",
        "category": "Population genetics",
        "description": "Ridge-regression genomic prediction from a marker matrix.",
        "inputs_arity": 2,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "dims": [{"param": "individual_dim", "default": "individual"}], "numeric": True, "ndim": 2}, {"version": 1, "dims": [{"param": "trait_dim", "default": "trait"}], "numeric": True, "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"]}, {"logical_type": "form", "representations": ["form"]}],
            "outputs": [{"logical_type": "form", "representations": ["form"]}],
        },
    }

    parameters_file = "genomic_selection_rrblup.GenomicSelectionRrblupStep.parameters.json"

    def run(self, ctx, inputs):
        form = inputs[0]
        pheno_form = inputs[1]
        y = column(pheno_form, "trait", ctx.step_params.get("phenotype_field", "phenotype"))
        X = np.asarray(form.data, dtype=float)
        if y.size != X.shape[0]:
            raise StepError("genomic_selection_rrblup: genotype rows and phenotype length differ")
        lam = float(ctx.step_params.get("lambda", 1.0))
        if lam <= 0:
            lam = 1.0
        mu = float(np.nanmean(y))
        yc = y - mu
        Xc = np.nan_to_num(X - X.mean(axis=0, keepdims=True), nan=0.0)
        A = Xc.T @ Xc + lam * np.eye(Xc.shape[1])
        b = np.linalg.solve(A, Xc.T @ yc)
        gebv = Xc @ b
        pred = mu + gebv
        resid = y - pred
        out = result_form(["observed", "predicted", "residual"], [y, pred, resid], "individual")
        out_name = ctx.step_params.get("output", "output")
        ctx[out_name] = out

    def export(self, ctx):
        out_name = ctx.step_params.get("output", "output")
        form = ctx[out_name]
        return {
            "result_files": [],
            "output": out_name,
            "dims": [str(dim) for dim in form.dims],
            "rows": int(form.data.shape[0]),
            "columns": [str(label) for label in form.labels.get(str(form.dims[1]), [])],
        }

    def estimate_memory(self, inputs, params, profiles):
        return {"bytes": 64 * 1024 * 1024}
