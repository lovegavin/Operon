"""Spectrum library match"""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.step.base import Step
from ._ms66_common import numeric_column, result_form, string_column


class SpectrumLibraryMatchStep(Step):
    definition = {
    "protocol_version": 3,
    "protocol_revision": "3.7",
    "id": "spectrum_library_match",
    "version": "1.0.0",
    "kind": "operator",
    "title": "Spectrum library match",
    "category": "Proteomics MS",
    "description": "Cosine score of each query spectrum against a library of spectra.",
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
                        "param": "query_dim",
                        "default": "query"
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
                        "param": "library_dim",
                        "default": "library"
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
    parameters_file = "spectrum_library_match.SpectrumLibraryMatchStep.parameters.json"

    def run(self, ctx, inputs):
        params = ctx.step_params
        q = inputs[0]
        lib = inputs[1]
        qid = numeric_column(q, "field", "query_id").astype(int)
        qmz = numeric_column(q, "field", "mz")
        qi = numeric_column(q, "field", "intensity")
        lid = numeric_column(lib, "field", "library_id").astype(int)
        lmz = numeric_column(lib, "field", "mz")
        li = numeric_column(lib, "field", "intensity")
        tol_ppm = float(params.get("tolerance_ppm", 20.0))
        min_score = float(params.get("min_score", 0.0))
        names = sorted(set(int(v) for v in qid))
        rows = []
        for name in names:
            m = qid == name
            qm, qv = qmz[m], qi[m]
            best = (0.0, 0.0, 0.0, -1.0)
            for lib_name in sorted(set(int(v) for v in lid)):
                mm = lid == lib_name
                lm, lv = lmz[mm], li[mm]
                score = 0.0
                matched = 0
                ppm = 0.0
                for a, b in zip(qm, qv):
                    diff = np.abs(lm - a) / max(a, 1e-9) * 1e6
                    j = int(np.argmin(diff)) if diff.size else -1
                    if j >= 0 and diff[j] <= tol_ppm:
                        score += float(b) * float(lv[j])
                        matched += 1
                        ppm += float(diff[j])
                denom = float(np.linalg.norm(qv) * np.linalg.norm(lv)) or 1.0
                score = min(1.0, max(0.0, score / denom))
                if score > best[0]:
                    best = (score, float(matched), ppm / matched if matched else 0.0, float(lib_name))
            if best[0] >= min_score:
                rows.append([round(best[0], 9), best[1], round(best[2], 6), best[3]])
            else:
                rows.append([np.nan, np.nan, np.nan, np.nan])
        columns = ["cosine", "matched_peaks", "mean_ppm", "library_id"]
        out = result_form(names, rows, columns)
        ctx[params["output"]] = out

        return None
