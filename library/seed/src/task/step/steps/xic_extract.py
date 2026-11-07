"""b68 xic_extract."""
from __future__ import annotations

import numpy as np
from scipy import stats as st

from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b68_common import numeric_column, result_form, string_column


class XicExtractStep(Step):
    definition = {
    "protocol_version": 3,
    "id": "xic_extract",
    "version": "1.0.0",
    "kind": "operator",
    "title": "Extracted ion chromatogram peaks",
    "category": "Metabolomics",
    "description": "Detect and integrate peaks in a single extracted-ion chromatogram.",
    "icon": "Table",
    "inputs_arity": 1,
    "output_parameter": "output",
    "outputs": [],
    "data_formats": {
        "inputs": [
            {
                "logical_type": "form",
                "representations": [
                    "form"
                ]
            }
        ],
        "outputs": [
            {
                "logical_type": "form",
                "representations": [
                    "form"
                ]
            }
        ]
    },
    "contracts": {
        "version": 1,
        "inputs": [
            {
                "version": 1,
                "numeric": True,
                "ndim": 2,
                "dims": [
                    {
                        "param": "scan_dim",
                        "default": "scan"
                    },
                    {
                        "param": "field_dim",
                        "default": "field"
                    }
                ],
                "labels": [],
                "parallel": []
            }
        ],
        "output": {
            "mode": "declare",
            "schema": {
                "ndim": 2,
                "numeric": True
            }
        }
    },
    "resources": {
        "memory_modes": [
            "full"
        ],
        "supports_cuda": False,
        "estimate": "estimate_memory"
    }
}
    parameters_file = "xic_extract.XicExtractStep.parameters.json"

    def run(self, ctx, inputs):
        min_snr = ctx.step_params.get('min_snr', 3.0)
        smoothing = ctx.step_params.get('smoothing', 3)
        scan_dim = ctx.step_params.get('scan_dim', 'scan')
        field_dim = ctx.step_params.get('field_dim', 'field')
        apex_rt = ctx.step_params.get('apex_rt', 'apex_rt')
        apex_intensity = ctx.step_params.get('apex_intensity', 'apex_intensity')
        area = ctx.step_params.get('area', 'area')
        start_rt = ctx.step_params.get('start_rt', 'start_rt')
        end_rt = ctx.step_params.get('end_rt', 'end_rt')
        snr = ctx.step_params.get('snr', 'snr')
        rt = numeric_column(inputs[0], scan_dim, "rt")
        intensity = numeric_column(inputs[0], scan_dim, "intensity")
        if rt.size < 3:
            raise ValueError("XIC needs at least three scans")
        order = np.argsort(rt)
        rt, intensity = rt[order], intensity[order]
        if smoothing > 1:
            kernel = np.ones(int(smoothing)) / float(smoothing)
            smooth = np.convolve(intensity, kernel, mode="same")
        else:
            smooth = intensity
        noise = float(np.median(np.abs(np.diff(smooth)))) or 1.0
        peaks = []
        for i in range(1, len(smooth) - 1):
            if smooth[i] >= smooth[i - 1] and smooth[i] > smooth[i + 1] and smooth[i] / noise >= min_snr:
                left = i
                while left > 0 and smooth[left - 1] <= smooth[left]:
                    left -= 1
                right = i
                while right < len(smooth) - 1 and smooth[right + 1] <= smooth[right]:
                    right += 1
                area = float(np.trapezoid(intensity[left:right + 1], rt[left:right + 1]))
                peaks.append([round(float(rt[i])), round(float(intensity[i])), round(abs(float(area)), 6), round(float(rt[left])), round(float(rt[right])), round(float(smooth[i] / noise), 6)])
        out = result_form([f"peak{i}" for i in range(len(peaks))], peaks,
                  columns=["apex_rt", "apex_intensity", "area", "start_rt", "end_rt", "snr"])
        ctx[ctx.step_params["output"]] = out
