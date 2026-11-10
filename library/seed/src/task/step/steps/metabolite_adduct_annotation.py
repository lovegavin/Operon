"""b68 metabolite_adduct_annotation."""
from __future__ import annotations

import numpy as np
from scipy import stats as st

from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b68_common import numeric_column, result_form, string_column


class MetaboliteAdductAnnotationStep(Step):
    definition = {
    "protocol_version": 3,
    "id": "metabolite_adduct_annotation",
    "version": "1.0.0",
    "kind": "operator",
    "title": "Metabolite adduct annotation",
    "category": "Metabolomics",
    "description": "Convert feature m/z values into neutral masses for common adducts and match a database.",
    "icon": "Table",
    "inputs_arity": 2,
    "output_parameter": "output",
    "outputs": [],
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
                "version": 1,
                "numeric": True,
                "ndim": 2,
                "dims": [
                    {
                        "param": "feature_dim",
                        "default": "feature"
                    },
                    {
                        "param": "field_dim",
                        "default": "field"
                    }
                ],
                "labels": [],
                "parallel": []
            },
            {
                "version": 1,
                "numeric": True,
                "ndim": 2,
                "dims": [
                    {
                        "param": "entry_dim",
                        "default": "entry"
                    },
                    {
                        "param": "db_field_dim",
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
    parameters_file = "metabolite_adduct_annotation.MetaboliteAdductAnnotationStep.parameters.json"

    def run(self, ctx, inputs):
        ppm_tolerance = ctx.step_params.get('ppm_tolerance', 10.0)
        polarity = ctx.step_params.get('polarity', 'positive')
        feature_dim = ctx.step_params.get('feature_dim', 'feature')
        field_dim = ctx.step_params.get('field_dim', 'field')
        entry_dim = ctx.step_params.get('entry_dim', 'entry')
        db_field_dim = ctx.step_params.get('db_field_dim', 'field')
        neutral_mass = ctx.step_params.get('neutral_mass', 'neutral_mass')
        best_entry_index = ctx.step_params.get('best_entry_index', 'best_entry_index')
        ppm_error = ctx.step_params.get('ppm_error', 'ppm_error')
        adduct_code = ctx.step_params.get('adduct_code', 'adduct_code')
        matched = ctx.step_params.get('matched', 'matched')
        forms = inputs
        feat, db = forms[0], forms[1]
        mz = numeric_column(feat, feature_dim, "mz")
        db_mass = numeric_column(db, entry_dim, "neutral_mass")
        db_names = list(db.labels.get(entry_dim, {}).keys())
        if polarity == "positive":
            adducts = [("M+H", 1.007276466621), ("M+Na", 22.9892180), ("M+NH4", 18.0338230)]
        else:
            adducts = [("M-H", -1.007276466621)]
        rows = []
        for value in mz:
            best = (0.0, -1, float("nan"), 0, 0.0)
            for code, (label, shift) in enumerate(adducts, start=1):
                neutral = value - shift
                ppm = np.abs(db_mass - neutral) / neutral * 1e6
                j = int(np.argmin(ppm)) if ppm.size else -1
                if j >= 0 and ppm[j] <= ppm_tolerance and (best[1] < 0 or ppm[j] < best[2]):
                    best = (neutral, j, float(ppm[j]), code, 1.0)
            rows.append([round(float(v), 12) if isinstance(v, float) else v for v in best])
        names = sorted(feat.labels.get(feature_dim, {})) or [f"feature{i}" for i in range(len(mz))]
        out = result_form(names, rows,
                          {"adduct_labels": [a[0] for a in adducts]},
                          columns=["neutral_mass", "best_entry_index", "ppm_error", "adduct_code", "matched"])
        ctx[ctx.step_params["output"]] = out
