"""Pairwise peak overlap matrix"""
import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b62_common import names, numeric, strings, table


class PeakOverlapMatrixStep(Step):
    parameters_file = "peak_overlap_matrix.PeakOverlapMatrixStep.parameters.json"

    definition = {
    "id": "peak_overlap_matrix",
    "version": "1.0.0",
    "title": "Pairwise peak overlap matrix",
    "description": "Pairwise peak overlap matrix",
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
                    "row2"
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

        peaks = inputs[0]
        names_ = names(peaks)
        start = numeric(peaks, peaks.dims[1], "start")
        end = numeric(peaks, peaks.dims[1], "end")
        chrom = strings(peaks, peaks.dims[1], "chrom")
        n = len(names_)
        mat = np.zeros((n, n), dtype=float)
        for i in range(n):
            for j in range(n):
                if chrom[i] != chrom[j]:
                    continue
                ov = min(end[i], end[j]) - max(start[i], start[j])
                mat[i, j] = max(0.0, ov)
        out = Form(data=np.round(mat, 9), dims=["row", "row2"],
                   labels={"row": {s: i for i, s in enumerate(names_)},
                           "row2": {s: i for i, s in enumerate(names_)}},
                   info={"columns": list(names_)})
        out.validate()
        ctx[ctx.step_params["output"]] = out

