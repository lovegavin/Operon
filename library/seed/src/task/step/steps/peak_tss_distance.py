"""Definition for the peak_tss_distance operator."""
import numpy as np
from src.core import StepError
from src.task.step.base import Step
from ._peak_common import decode_column, numeric_column
from ._peak_overlap_common import intervals, overlap, feature_rows, metric_form, win_form

class PeakTssDistanceStep(Step):
    definition = {
        "protocol_version": 3, "protocol_revision": "3.7", "id": "peak_tss_distance",
        "version": "1.0.0", "kind": "operator", "title": "Distance from peaks to nearest TSS",
        "category": "Epigenomics", "description": "Summarizes peak distance to the nearest gene TSS.",
        "inputs_arity": 2, "output_parameter": "output", "outputs": [],
        "contracts": {"version": 1,
            "inputs": [{"version": 1, "dims": [{"param": "region_dim", "default": "region"}, {"param": "field_dim", "default": "field"}], "numeric": False, "ndim": 2}, {"version": 1, "dims": [{"param": "record_dim", "default": "record"}, {"param": "field_dim", "default": "field"}], "numeric": False, "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}},
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "data_formats": {"inputs": [{"logical_type": "form", "representations": ["form"]}, {"logical_type": "form", "representations": ["form"]}], "outputs": [{"logical_type": "form", "representations": ["form"]}]},
    }
    parameters_file = "peak_tss_distance.PeakTssDistanceStep.parameters.json"

    def run(self, ctx, inputs):
        peaks, genes = inputs
        p = intervals(peaks)
        g = feature_rows(genes, types=("gene",))
        d = []
        for chrom, s, e in p:
            best = None
            for gs, gstart, gend, strand in g:
                if gs != chrom:
                    continue
                tss = gstart if strand == "+" else gend
                dist = (s + e) / 2.0 - tss
                if best is None or abs(dist) < abs(best):
                    best = dist
            if best is not None:
                d.append(best)
        a = np.abs(d)
        out = metric_form(["n_peaks", "n_with_tss", "mean_abs_distance", "median_abs_distance",
                            "mean_signed_distance", "frac_within_1kb", "frac_within_5kb"],
                           [len(p), len(d), float(a.mean()) if len(a) else 0.0,
                            float(np.median(a)) if len(a) else 0.0,
                            float(np.mean(d)) if len(d) else 0.0,
                            float((a <= 1000).mean()) if len(a) else 0.0,
                            float((a <= 5000).mean()) if len(a) else 0.0],
                           ctx.step_params.get("output", "output"))
        out.validate()
        ctx[ctx.step_params.get("output", "output")] = out

    def export(self, ctx):
        name = ctx.step_params.get("output", "output")
        f = ctx[name]
        return {"result_files": [], "output": name, "dims": [str(d) for d in f.dims],
                "rows": int(f.data.shape[0]), "columns": [str(x) for x in f.labels.get("statistic", [])]}
