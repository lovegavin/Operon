"""Scan sequences with a position weight matrix"""
import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b62_common import names, numeric, strings, table


class MotifScanPwmStep(Step):
    parameters_file = "motif_scan_pwm.MotifScanPwmStep.parameters.json"

    definition = {
    "id": "motif_scan_pwm",
    "version": "1.0.0",
    "title": "Scan sequences with a position weight matrix",
    "description": "Scan sequences with a position weight matrix",
    "category": "Epigenomics",
    "icon": "epigenomics",
    "kind": "operator",
    "protocol_version": 3,
    "protocol_revision": "3.7",
    "inputs_arity": 2,
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
            },
            {
                "name": "in2",
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
            },
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

        seqs, pwm = inputs
        seq_names = strings(seqs, seqs.dims[1], "seq")
        matrix = np.asarray(pwm.data, dtype=float)
        motif_len = matrix.shape[1]
        best = []
        for seq in seq_names:
            s = str(seq).upper()
            top, pos = -1e18, -1
            for k in range(0, max(0, len(s) - motif_len + 1)):
                score = 0.0
                ok = True
                for j in range(motif_len):
                    b = s[k + j]
                    row = "ACGT".find(b)
                    if row < 0:
                        ok = False
                        break
                    score += matrix[row, j]
                if ok and score > top:
                    top, pos = score, k
            best.append([top if pos >= 0 else float("nan"), pos])
        out = table(seq_names, best, ["best_score", "best_position"])
        ctx[ctx.step_params["output"]] = out

