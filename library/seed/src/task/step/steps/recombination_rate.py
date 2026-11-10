"""Definition for the recombination_rate operator."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step

from ._popgen_common import column, result_form, string_column


class RecombinationRateStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "recombination_rate",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Recombination rate from a genetic map",
        "category": "Population genetics",
        "description": "Local cM per Mb rates from cumulative genetic map positions.",
        "inputs_arity": 1,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "dims": [{"param": "interval_dim", "default": "interval"}, {"param": "field_dim", "default": "field"}], "numeric": True, "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"]}],
            "outputs": [{"logical_type": "form", "representations": ["form"]}],
        },
    }

    parameters_file = "recombination_rate.RecombinationRateStep.parameters.json"

    def run(self, ctx, inputs):
        form = inputs[0]
        chrom_values = string_column(form, "field", ctx.step_params.get("chrom_field", "chrom"))
        pos = column(form, "field", ctx.step_params.get("pos_field", "pos"))
        cm = column(form, "field", ctx.step_params.get("cm_field", "cM"))
        chrom = np.asarray(chrom_values)
        n = pos.size
        phys = np.zeros(n)
        dist = np.zeros(n)
        rate = np.zeros(n)
        cum = np.zeros(n)
        for i in range(n):
            if i == 0 or chrom[i] != chrom[i - 1]:
                continue
            dbp = float(pos[i] - pos[i - 1])
            dc = float(cm[i] - cm[i - 1])
            phys[i] = dbp
            dist[i] = dc
            cum[i] = float(cm[i] - cm[np.flatnonzero(chrom == chrom[i])[0]])
            rate[i] = dc / (dbp / 1e6) if dbp > 0 else 0.0
        rate = np.clip(rate, 0.0, None)
        out = result_form(["physical_distance_bp", "genetic_distance_cM", "rate_cM_per_Mb", "cumulative_cM"],
                          [phys, dist, rate, cum], "interval")
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
