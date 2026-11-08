"""Sobel gradient magnitude."""

from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step

from ._b84_common import matrix, row_names


class ImageSobelGradientStep(Step):
    parameters_file = "image_sobel_gradient.ImageSobelGradientStep.parameters.json"
    definition = {'protocol_version': 3, 'protocol_revision': '3.7', 'kind': 'operator', 'id': 'image_sobel_gradient', 'version': '1.0.0', 'title': 'Sobel gradient magnitude', 'description': 'Computes the Sobel gradient magnitude of a 2D image.', 'category': 'Statistics', 'icon': 'image', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    def run(self, ctx, inputs):
        data = matrix(inputs[0])
        kx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=float)
        ky = kx.T
        h, w = data.shape
        gx = np.zeros_like(data); gy = np.zeros_like(data)
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                patch = data[y - 1:y + 2, x - 1:x + 2]
                gx[y, x] = float((patch * kx).sum())
                gy[y, x] = float((patch * ky).sum())
        out = Form(np.sqrt(gx * gx + gy * gy), dims=list(inputs[0].dims), labels=dict(inputs[0].labels))
        ctx[ctx.step_params["output"]] = out
