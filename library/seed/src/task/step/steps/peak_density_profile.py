"""Definition for the peak_density_profile operator."""
import numpy as np
from src.core import StepError
from src.task.step.base import Step
from ._peak_common import decode_column, numeric_column
from ._peak_overlap_common import intervals, overlap, feature_rows, metric_form, win_form

class PeakDensityProfileStep(Step):
    definition = {
        "protocol_version": 3, "protocol_revision": "3.7", "id": "peak_density_profile",
        "version": "1.0.0", "kind": "operator", "title": "Peak density in fixed windows",
        "category": "Epigenomics", "description": "Counts peaks and covered bases per genomic window.",
        "inputs_arity": 2, "output_parameter": "output", "outputs": [],
        "contracts": {"version": 1,
            "inputs": [{"version": 1, "dims": [{"param": "region_dim", "default": "region"}, {"param": "field_dim", "default": "field"}], "numeric": False, "ndim": 2}, {"version": 1, "dims": [{"param": "chrom_dim", "default": "chrom"}, {"param": "field_dim", "default": "field"}], "numeric": False, "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}},
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "data_formats": {"inputs": [{"logical_type": "form", "representations": ["form"]}, {"logical_type": "form", "representations": ["form"]}], "outputs": [{"logical_type": "form", "representations": ["form"]}]},
    }
    parameters_file = "peak_density_profile.PeakDensityProfileStep.parameters.json"

    def run(self, ctx, inputs):
        peaks, genome = inputs
        p = intervals(peaks)
        chroms = list(genome.labels["chrom"].keys())
        sizes = numeric_column(genome, "field", "size")
        w = int(ctx.step_params.get("window_bp", 1000000))
        rows = []
        for chrom, size in zip(chroms, sizes):
            if not np.isfinite(size):
                continue
            size = int(size)
            for start in range(0, size, w):
                end = min(start + w, size)
                sub = [x for x in p if x[0] == chrom and x[1] < end and x[2] > start]
                covered = sum(max(0, min(x[2], end) - max(x[1], start)) for x in sub)
                rows.append((chrom, start // w + 1, len(sub), covered, len(sub) * 1e6 / (end - start)))
        out = win_form(rows)
        out.validate()
        ctx[ctx.step_params.get("output", "output")] = out

    def export(self, ctx):
        name = ctx.step_params.get("output", "output")
        f = ctx[name]
        return {"result_files": [], "output": name, "dims": [str(d) for d in f.dims],
                "rows": int(f.data.shape[0]), "columns": [str(x) for x in f.labels.get("statistic", [])]}
