"""MS1 profile peak detection per scan."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._ms68_common import column, row_labels, tabular


class Ms1FeatureDetectStep(Step):
    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "ms1_feature_detect",
        "version": "1.0.0",
        "kind": "operator",
        "title": "MS1 feature detection",
        "category": "Metabolomics",
        "icon": "Chart",
        "description": "Detect local intensity maxima in profile-mode MS1 scans.",
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"]}],
            "outputs": [{"logical_type": "form", "representations": ["form"]}],
        },
        "contracts": {
            "version": 1,
            "inputs": [{"dims": [{"param": "peak_dim", "default": "peak"},
                                 {"param": "field_dim", "default": "field"}]}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False,
                      "estimate": "estimate_memory"},
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }
    parameters_file = "ms1_feature_detect.Ms1FeatureDetectStep.parameters.json"

    def run(self, ctx, inputs):
        form = inputs[0]
        scan_dim = ctx.step_params.get("scan_dim", "scan")
        field_dim = ctx.step_params.get("field_dim", "field")
        output = ctx.step_params.get("output", "features")
        min_intensity = float(ctx.step_params.get("min_intensity", 1000.0))
        min_prominence = float(ctx.step_params.get("min_prominence", 100.0))
        mz = column(form, field_dim, "mz")
        intensity = column(form, field_dim, "intensity")
        scan_values = column(form, field_dim, "scan")
        groups = {}
        for i, scan in enumerate(scan_values):
            groups.setdefault(int(scan), []).append(i)
        rows = []
        for scan in sorted(groups):
            idx = sorted(groups[scan], key=lambda i: mz[i])
            for j in range(1, len(idx) - 1):
                a, b, c = idx[j - 1], idx[j], idx[j + 1]
                if intensity[b] <= intensity[a] or intensity[b] <= intensity[c]:
                    continue
                if intensity[b] < min_intensity:
                    continue
                if intensity[b] - max(intensity[a], intensity[c]) < min_prominence:
                    continue
                rows.append([mz[b], intensity[b], float(b), scan])
        data = np.asarray(rows, dtype=float) if rows else np.zeros((0, 4))
        labels = {"feature": {str(i): i for i in range(data.shape[0])},
                  "statistic": {"mz": 0, "intensity": 1, "peak_index": 2, "scan": 3}}
        out = tabular(["feature", "statistic"], labels, data, "features",
                      {"n_scans": len(groups)})
        ctx[output] = out

    def export(self, ctx):
        return {"format": "form"}
