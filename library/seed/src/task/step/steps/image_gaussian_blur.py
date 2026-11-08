"""Gaussian image blur (b95)."""

from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._b95_common import column, columns, matrix, table


class ImageGaussianBlurStep(Step):
    parameters_file = "image_gaussian_blur.ImageGaussianBlurStep.parameters.json"
    definition = {'id': 'image_gaussian_blur', 'version': '1.0.0', 'title': 'Gaussian image blur', 'description': 'Separable Gaussian blur with reflect padding for 2D image matrices.', 'category': 'Imaging', 'icon': 'blur', 'protocol_version': 3, 'protocol_revision': '3.7', 'kind': 'operator', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': True, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}

    def run(self, ctx, inputs):
        image = np.asarray(inputs[0].data, dtype=float)
        if image.ndim != 2:
            raise ValueError("image blur expects a 2D matrix")
        sigma = float(ctx.step_params.get("sigma", 1.5))
        truncate = float(ctx.step_params.get("truncate", 4.0))
        if sigma <= 0:
            out = image.copy()
        else:
            radius = max(1, int(truncate * sigma + 0.5))
            x = np.arange(-radius, radius + 1)
            kernel = np.exp(-(x ** 2) / (2 * sigma ** 2))
            kernel /= kernel.sum()
            pad = np.pad(image, radius, mode="symmetric")
            tmp = np.apply_along_axis(lambda v: np.convolve(v, kernel, mode="valid"), 1, pad)
            out = np.apply_along_axis(lambda v: np.convolve(v, kernel, mode="valid"), 0, tmp)
        ctx[ctx.step_params["output"]] = Form(data=np.round(out, 9), dims=list(inputs[0].dims),
                                              labels=inputs[0].labels)
