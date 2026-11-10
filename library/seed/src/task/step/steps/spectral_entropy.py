"""Spectral entropy and peak complexity"""
import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b62b_common import column, string_column, table

class SpectralEntropyStep(Step):
    parameters_file = "spectral_entropy.SpectralEntropyStep.parameters.json"

    definition = {
        "id": "spectral_entropy",
        "version": "1.0.0",
        "title": "Spectral entropy and peak complexity",
        "description": "Spectral entropy and peak complexity",
        "category": "Proteomics",
        "icon": "Table",
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "kind": "operator",
        "inputs_arity": 1,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "numeric": True, "dims": [{"param": "row_dim", "default": "row"}, {"param": "field_dim", "default": "field"}], "labels": [], "parallel": [], "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
        },
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"]}],
            "outputs": [{"logical_type": "form", "representations": ["form"]}]
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"}
    }

    def run(self, ctx, inputs):

        spectra = string_column(inputs[0], "spectrum")
        mz = column(inputs[0], "mz")
        inten = column(inputs[0], "intensity")
        rows = []
        vals = []
        for s in sorted(set(spectra)):
            sel = np.array([x == s for x in spectra])
            p = np.clip(inten[sel], 0, None)
            p = p / p.sum() if p.sum() > 0 else p
            nz = p[p > 0]
            ent = float(-(nz * np.log2(nz)).sum()) if nz.size else 0.0
            rows.append(s)
            vals.append([float(sel.sum()), ent, ent / np.log2(max(sel.sum(), 2)), float(np.sort(p)[-max(1, int(0.1 * len(p))):].sum())])
        ctx[ctx.step_params["output"]] = table(rows, ["n_peaks", "entropy", "normalized_entropy", "top10_fraction"], vals)
        return None
