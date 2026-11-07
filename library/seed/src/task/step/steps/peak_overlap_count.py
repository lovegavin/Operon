"""Definition for the peak_overlap_count operator."""
import numpy as np
from src.core import StepError
from src.task.step.base import Step
from ._peak_common import decode_column, numeric_column
from ._peak_overlap_common import intervals, overlap, feature_rows, metric_form, win_form

class PeakOverlapCountStep(Step):
    definition = {
        "protocol_version": 3, "protocol_revision": "3.7", "id": "peak_overlap_count",
        "version": "1.0.0", "kind": "operator", "title": "Count peaks overlapping genes",
        "category": "Epigenomics", "description": "Counts how many peaks overlap any gene feature.",
        "inputs_arity": 2, "output_parameter": "output", "outputs": [],
        "contracts": {"version": 1,
            "inputs": [{"version": 1, "dims": [{"param": "region_dim", "default": "region"}, {"param": "field_dim", "default": "field"}], "numeric": False, "ndim": 2}, {"version": 1, "dims": [{"param": "record_dim", "default": "record"}, {"param": "field_dim", "default": "field"}], "numeric": False, "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}},
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"},
        "data_formats": {"inputs": [{"logical_type": "form", "representations": ["form"]}, {"logical_type": "form", "representations": ["form"]}], "outputs": [{"logical_type": "form", "representations": ["form"]}]},
    }
    parameters_file = "peak_overlap_count.PeakOverlapCountStep.parameters.json"

    def run(self, ctx, inputs):
        peaks, genes = inputs
        p = intervals(peaks)
        g = feature_rows(genes, types=("gene",))
        n = len(p)
        hits = [x for x in p if any(overlap(x, y) for y in g)]
        bp = sum(max(0, min(pe, ge) - max(ps, gs)) for pc, ps, pe in hits for gc, gs, ge, st in g if pc == gc and ps < ge and gs < pe)
        out = metric_form(["n_peaks", "n_overlapping", "fraction_overlapping", "overlap_bp"],
                           [n, len(hits), len(hits) / n if n else 0.0, bp])
        out.validate()
        ctx[ctx.step_params.get("output", "output")] = out

    def export(self, ctx):
        name = ctx.step_params.get("output", "output")
        f = ctx[name]
        return {"result_files": [], "output": name, "dims": [str(d) for d in f.dims],
                "rows": int(f.data.shape[0]), "columns": [str(x) for x in f.labels.get("statistic", [])]}
