"""MS2 cosine similarity against a library spectrum"""
import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b62b_common import column, string_column, table

class Ms2CosineSimilarityStep(Step):
    parameters_file = "ms2_cosine_similarity.Ms2CosineSimilarityStep.parameters.json"

    definition = {
        "id": "ms2_cosine_similarity",
        "version": "1.0.0",
        "title": "MS2 cosine similarity against a library spectrum",
        "description": "MS2 cosine similarity against a library spectrum",
        "category": "Proteomics",
        "icon": "Table",
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "kind": "operator",
        "inputs_arity": 2,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "numeric": True, "dims": [{"param": "row_dim", "default": "row"}, {"param": "field_dim", "default": "field"}], "labels": [], "parallel": [], "ndim": 2}, {"version": 1, "numeric": True, "dims": [{"param": "row_dim", "default": "row"}, {"param": "field_dim", "default": "field"}], "labels": [], "parallel": [], "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
        },
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"]}, {"logical_type": "form", "representations": ["form"]}],
            "outputs": [{"logical_type": "form", "representations": ["form"]}]
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"}
    }

    def run(self, ctx, inputs):

        qsp = string_column(inputs[0], "spectrum")
        qmz = column(inputs[0], "mz")
        qi = column(inputs[0], "intensity")
        lsp = string_column(inputs[1], "spectrum")
        lmz = column(inputs[1], "mz")
        li = column(inputs[1], "intensity")
        tol = float(ctx.step_params.get("fragment_ppm", 20.0))
        rows = []
        vals = []
        for q in sorted(set(qsp)):
            qsel = np.array([x == q for x in qsp])
            qm = qmz[qsel]
            qv = qi[qsel]
            qv = qv / qv.max() if qv.max() > 0 else qv
            best = (0.0, 0, 0.0, "")
            best_ids = {}
            for lib in sorted(set(lsp)):
                lsel = np.array([x == lib for x in lsp])
                lm = lmz[lsel]
                lv = li[lsel]
                lv = lv / lv.max() if lv.max() > 0 else lv
                matched = 0
                ppm = []
                prod = 0.0
                for a, va in zip(qm, qv):
                    j = int(np.argmin(np.abs(lm - a)))
                    if lm.size and abs(lm[j] - a) / a * 1e6 <= tol:
                        prod += va * lv[j]
                        matched += 1
                        ppm.append(abs(lm[j] - a) / a * 1e6)
                cos = prod / (np.linalg.norm(qv) * np.linalg.norm(lv)) if np.linalg.norm(qv) > 0 and np.linalg.norm(lv) > 0 else 0.0
                if cos > best[0]:
                    best = (float(cos), matched, float(np.mean(ppm)) if ppm else 0.0, lib)
            rows.append(q)
            best_ids[q] = best[3]
            vals.append(list(best[:3]))
        out = table(rows, ["cosine", "matched_peaks", "mean_ppm"], vals)
        out.info["library_spectrum"] = best_ids
        ctx[ctx.step_params["output"]] = out
        return None
