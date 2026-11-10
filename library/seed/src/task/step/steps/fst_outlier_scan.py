"""Definition for the fst_outlier_scan operator."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.step.base import Step

from ._popgen_common import column, result_form, string_column


class FstOutlierScanStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "fst_outlier_scan",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Fst outlier scan",
        "category": "Population genetics",
        "description": "Hudson Fst per variant with local smoothing and outlier flags.",
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

    parameters_file = "fst_outlier_scan.FstOutlierScanStep.parameters.json"

    def run(self, ctx, inputs):
        form = inputs[0]
        field = "field"
        chrom_values = string_column(form, "field", ctx.step_params.get("chrom_field", "chrom"))
        pos_values = column(form, field, ctx.step_params.get("pos_field", "pos"))
        ref1 = column(form, field, ctx.step_params.get("ref1_field", "n1_ref"))
        alt1 = column(form, field, ctx.step_params.get("alt1_field", "n1_alt"))
        ref2 = column(form, field, ctx.step_params.get("ref2_field", "n2_ref"))
        alt2 = column(form, field, ctx.step_params.get("alt2_field", "n2_alt"))
        n1 = ref1 + alt1
        n2 = ref2 + alt2
        with np.errstate(divide="ignore", invalid="ignore"):
            p1 = np.where(n1 > 0, alt1 / n1, np.nan)
            p2 = np.where(n2 > 0, alt2 / n2, np.nan)
            num = (p1 - p2) ** 2 - p1 * (1.0 - p1) / (n1 - 1.0) - p2 * (1.0 - p2) / (n2 - 1.0)
            den = p1 * (1.0 - p2) + p2 * (1.0 - p1)
            fst = np.where((n1 > 1) & (n2 > 1) & (den > 0), num / den, 0.0)
        fst = np.clip(np.nan_to_num(fst, nan=0.0), 0.0, 1.0)
        window_bp = float(ctx.step_params.get("window_bp", 100000))
        threshold = float(ctx.step_params.get("z_threshold", 3.0))
        chrom = np.asarray(chrom_values)
        pos = np.asarray(pos_values, dtype=float)
        smooth = np.zeros_like(fst)
        z = np.zeros_like(fst)
        for i in range(fst.size):
            if not np.isfinite(pos[i]):
                smooth[i] = fst[i]
                continue
            mask = (chrom == chrom[i]) & (np.abs(pos - pos[i]) <= window_bp)
            vals = fst[mask]
            smooth[i] = vals.mean() if vals.size else fst[i]
            if mask.sum() > 2:
                sd = vals.std(ddof=1)
                if sd > 0:
                    z[i] = (fst[i] - smooth[i]) / sd
        outlier = (z > threshold).astype(float)
        out = result_form(["fst", "window_mean_fst", "z_score", "outlier"],
                          [fst, smooth, z, outlier], "variant")
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
