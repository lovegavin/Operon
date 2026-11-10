"""Otsu image threshold."""

from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step

from ._b84_common import matrix, row_names


class ImageOtsuThresholdStep(Step):
    parameters_file = "image_otsu_threshold.ImageOtsuThresholdStep.parameters.json"
    definition = {'protocol_version': 3, 'protocol_revision': '3.7', 'kind': 'operator', 'id': 'image_otsu_threshold', 'version': '1.0.0', 'title': 'Otsu image threshold', 'description': 'Computes a global Otsu threshold and the corresponding between-class variance.', 'category': 'Statistics', 'icon': 'image', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    def run(self, ctx, inputs):
        data = matrix(inputs[0])
        vals = np.unique(data)
        if vals.size < 2:
            thr = float(vals[0]); sigma_max = 0.0; fg = 0.0
        else:
            cands = (vals[:-1] + vals[1:]) / 2.0
            best = -1.0; thr = float(cands[0])
            for c in cands:
                left = data <= c
                w1 = float(left.mean())
                w0 = 1.0 - w1
                if w0 <= 0 or w1 <= 0:
                    continue
                mu0 = float(data[left].mean()); mu1 = float(data[~left].mean())
                sig = w0 * w1 * (mu1 - mu0) ** 2
                if sig > best + 1e-15:
                    best = sig; thr = float(c); fg = w1
            sigma_max = max(best, 0.0)
        out_data = np.array([[thr, float(sigma_max), float(fg)]], dtype=float)
        out = Form(
            out_data,
            dims=["entry", "statistic"],
            labels={"entry": {"otsu": 0}, "statistic": {"threshold": 0, "between_class_variance": 1, "foreground_fraction": 2}},
        )
        ctx[ctx.step_params["output"]] = out
