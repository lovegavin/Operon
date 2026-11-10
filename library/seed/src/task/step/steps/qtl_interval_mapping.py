"""Definition for the qtl_interval_mapping operator."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step

from ._popgen_common import column, result_form, string_column


class QtlIntervalMappingStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "qtl_interval_mapping",
        "version": "1.0.0",
        "kind": "operator",
        "title": "QTL interval mapping",
        "category": "Population genetics",
        "description": "Single-marker regression of a phenotype on marker dosage.",
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

    parameters_file = "qtl_interval_mapping.QtlIntervalMappingStep.parameters.json"

    def run(self, ctx, inputs):
        form = inputs[0]
        pheno_form = inputs[1]
        y = column(pheno_form, "trait", ctx.step_params.get("phenotype_field", "phenotype"))
        genotype = np.asarray(form.data, dtype=float)
        if y.size != genotype.shape[0]:
            raise StepError("qtl_interval_mapping: genotype rows and phenotype length differ")
        y = y - y.mean()
        m = genotype.shape[1]
        beta = np.zeros(m)
        se = np.zeros(m)
        tstat = np.zeros(m)
        pval = np.ones(m)
        lod = np.zeros(m)
        for j in range(m):
            x = np.nan_to_num(genotype[:, j].astype(float), nan=0.0)
            x = x - x.mean()
            sxx = float(np.sum(x * x))
            if sxx <= 0:
                continue
            b = float(np.sum(x * y) / sxx)
            resid = y - b * x
            dof = y.size - 2
            s2 = float(np.sum(resid * resid) / dof) if dof > 0 else np.nan
            if not np.isfinite(s2):
                continue
            beta[j] = b
            se[j] = np.sqrt(s2 / sxx)
            tstat[j] = b / se[j] if se[j] > 0 else 0.0
            try:
                from scipy import stats
                pval[j] = float(2.0 * stats.t.sf(abs(tstat[j]), dof))
            except Exception:
                pval[j] = 1.0
            lod[j] = -np.log10(max(pval[j], 1e-300))
        out = result_form(["beta", "se", "t_statistic", "p_value", "lod"],
                          [beta, se, tstat, pval, lod], "marker")
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
