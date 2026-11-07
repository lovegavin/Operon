"""Threshold-run chromatin segmentation"""
import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b62_common import names, numeric, strings, table


class ChromatinStateSegmentationStep(Step):
    parameters_file = "chromatin_state_segmentation.ChromatinStateSegmentationStep.parameters.json"

    definition = {
    "id": "chromatin_state_segmentation",
    "version": "1.0.0",
    "title": "Threshold-run chromatin segmentation",
    "description": "Threshold-run chromatin segmentation",
    "category": "Epigenomics",
    "icon": "epigenomics",
    "kind": "operator",
    "protocol_version": 3,
    "protocol_revision": "3.7",
    "inputs_arity": 1,
    "outputs": [],
    "output_parameter": "output",
    "contracts": {
        "version": 1,
        "inputs": [
            {
                "name": "in1",
                "dims": [
                    "row",
                    "field"
                ]
            }
        ],
        "output": {
            "mode": "declare",
            "schema": {
                "dims": [
                    "row",
                    "statistic"
                ],
                "logical_type": "form",
                "representations": [
                    "form"
                ]
            }
        }
    },
    "resources": {
        "memory_modes": [
            "full"
        ],
        "supports_cuda": False,
        "estimate": "estimate_memory"
    },
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
    }
}

    def run(self, ctx, inputs):

        track = inputs[0]
        pos = numeric(track, track.dims[1], "pos")
        signal = numeric(track, track.dims[1], "signal")
        thr = float(ctx.step_params.get("threshold", 1.0))
        min_len = int(ctx.step_params.get("min_length", 2))
        rows = []
        start = 0
        for i in range(1, len(signal) + 1):
            if i == len(signal) or (signal[i] >= thr) != (signal[start] >= thr):
                length = i - start
                if length >= min_len:
                    rows.append([pos[start], pos[i - 1], length,
                                 float(np.mean(signal[start:i])), 1.0 if signal[start] >= thr else 0.0])
                start = i
        out = table(["seg%d" % k for k in range(len(rows))], rows,
                    ["start", "end", "length", "mean_signal", "state"])
        out.info["n_segments"] = len(rows)
        ctx[ctx.step_params["output"]] = out

