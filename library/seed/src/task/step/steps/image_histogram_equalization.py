"""Histogram equalization."""

from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step

from ._b84_common import matrix, row_names


class ImageHistogramEqualizationStep(Step):
    parameters_file = "image_histogram_equalization.ImageHistogramEqualizationStep.parameters.json"
    definition = {'protocol_version': 3, 'protocol_revision': '3.7', 'kind': 'operator', 'id': 'image_histogram_equalization', 'version': '1.0.0', 'title': 'Histogram equalization', 'description': 'Global histogram equalization of a 2D image.', 'category': 'Statistics', 'icon': 'image', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    def run(self, ctx, inputs):
        data = matrix(inputs[0])
        lo = float(data.min()); hi = float(data.max())
        if hi <= lo:
            hi = lo + 1.0
        hist, edges = np.histogram(data, bins=256, range=(lo, hi))
        cdf = np.cumsum(hist).astype(float) / max(hist.sum(), 1)
        idx = np.clip(((data - lo) / (hi - lo) * 256).astype(int), 0, 255)
        out_data = cdf[idx]
        out = Form(out_data, dims=list(inputs[0].dims), labels=dict(inputs[0].labels))
        ctx[ctx.step_params["output"]] = out
