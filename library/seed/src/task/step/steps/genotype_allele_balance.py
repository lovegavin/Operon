"""Definition for the genotype_allele_balance operator."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step

from ._popgen_common import column, result_form, string_column


class GenotypeAlleleBalanceStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "genotype_allele_balance",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Genotype allele balance",
        "category": "Population genetics",
        "description": "Binomial allele-balance test from reference and alternate read counts.",
        "inputs_arity": 1,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "dims": [{"param": "variant_dim", "default": "variant"}, {"param": "field_dim", "default": "field"}], "numeric": True, "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"]}],
            "outputs": [{"logical_type": "form", "representations": ["form"]}],
        },
    }

    parameters_file = "genotype_allele_balance.GenotypeAlleleBalanceStep.parameters.json"

    def run(self, ctx, inputs):
        form = inputs[0]
        ref_c = column(form, "field", ctx.step_params.get("ref_field", "ref_count"))
        alt_c = column(form, "field", ctx.step_params.get("alt_field", "alt_count"))
        total = ref_c + alt_c
        frac = np.where(total > 0, alt_c / total, np.nan)
        pval = np.ones(total.size)
        try:
            from scipy.stats import binomtest
            for i in range(total.size):
                n = int(total[i])
                if n > 0:
                    pval[i] = float(binomtest(int(alt_c[i]), n, 0.5).pvalue)
        except Exception:
            pval[:] = np.nan
        threshold = float(ctx.step_params.get("p_threshold", 1e-3))
        flag = ((pval < threshold) | (frac < 0.2) | (frac > 0.8)).astype(float)
        flag[~np.isfinite(frac)] = np.nan
        out = result_form(["depth", "alt_fraction", "p_value", "imbalance_flag"],
                          [total, frac, pval, flag], "variant")
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
