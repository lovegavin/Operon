"""Peptide spectrum annotation"""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._ms66_common import numeric_column, result_form, string_column


class PeptideSpectrumAnnotationStep(Step):
    definition = {
    "protocol_version": 3,
    "protocol_revision": "3.7",
    "id": "peptide_spectrum_annotation",
    "version": "1.0.0",
    "kind": "operator",
    "title": "Peptide spectrum annotation",
    "category": "Proteomics MS",
    "description": "Theoretical b/y ion matching and coverage for each peptide.",
    "inputs_arity": 2,
    "outputs": [],
    "output_parameter": "output",
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
    },
    "contracts": {
        "version": 1,
        "inputs": [
            {
                "dims": [
                    {
                        "param": "peptide_dim",
                        "default": "peptide"
                    },
                    {
                        "param": "field_dim",
                        "default": "field"
                    }
                ]
            },
            {
                "dims": [
                    {
                        "param": "peak_dim",
                        "default": "peak"
                    },
                    {
                        "param": "field_dim",
                        "default": "field"
                    }
                ]
            }
        ],
        "output": {
            "mode": "declare",
            "schema": {
                "ndim": 2,
                "numeric": True,
                "info_open": True
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
    parameters_file = "peptide_spectrum_annotation.PeptideSpectrumAnnotationStep.parameters.json"

    def run(self, ctx, inputs):
        params = ctx.step_params
        pep = inputs[0]
        peaks = inputs[1]
        seqs = [s.upper() for s in string_column(pep, "field", "peptide")]
        spec = numeric_column(peaks, "field", "spectrum_id").astype(int)
        mz = numeric_column(peaks, "field", "mz")
        tol = float(params.get("tolerance_da", 0.02))
        masses = {
            "G": 57.02146, "A": 71.03711, "S": 87.03203, "P": 97.05276,
            "V": 99.06841, "T": 101.04768, "C": 103.00919, "L": 113.08406,
            "I": 113.08406, "N": 114.04293, "D": 115.02694, "Q": 128.05858,
            "K": 128.09496, "E": 129.04259, "M": 131.04049, "H": 137.05891,
            "F": 147.06841, "R": 156.10111, "Y": 163.06333, "W": 186.07931,
        }
        rows = []
        for i, seq in enumerate(seqs):
            theoretical = []
            total = sum(masses.get(a, 0.0) for a in seq)
            acc = 0.0
            for j, aa in enumerate(seq[:-1]):
                acc += masses.get(aa, 0.0)
                theoretical.append(acc + 1.007276)             # b ion
                theoretical.append(total - acc + 18.010565 + 1.007276)  # y ion
            m = spec == i
            observed = mz[m]
            hits = 0
            err = 0.0
            for t in theoretical:
                if observed.size:
                    d = np.abs(observed - t).min()
                    if d <= tol:
                        hits += 1
                        err += float(d)
            coverage = hits / max(1, len(theoretical))
            rows.append([float(hits), float(len(theoretical)), coverage, err / hits if hits else 0.0])
        columns = ["matched_ions", "theoretical_ions", "coverage", "mean_abs_error"]
        names = [f"pep{i}" for i in range(len(seqs))]
        ctx[params["output"]] = result_form(names, rows, columns)

        return None
