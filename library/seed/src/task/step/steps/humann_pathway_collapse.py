import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b58b_common import matrix_form, strings




class HumannPathwayCollapseStep(Step):

    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "humann_pathway_collapse",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Collapse stratified HUMAnN pathways to community totals",
        "category": "Metagenomics",
        "icon": "Table",
        "description": "Sum stratified pathway rows (pathway|taxon) into one row per pathway.",
        "inputs_arity": 1,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "taxon_dim", "default": "taxon"},
                        {"param": "sample_dim", "default": "sample"}
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}
            }
        },
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"]}],
            "outputs": [{"logical_type": "form", "representations": ["form"]}]
        },
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": False,
            "estimate": "estimate_memory"
        }
    }
    parameters_file = "humann_pathway_collapse.HumannPathwayCollapseStep.parameters.json"

    def run(self, ctx, inputs):
        names = strings(inputs[0], "taxon")
        cols = sorted((inputs[0].labels.get("sample", {}) or {}).items(), key=lambda kv: kv[1])
        columns = [k for k, _ in cols]
        data = inputs[0].data
        agg = {}
        for i, name in enumerate(names):
            key = name.split("|")[0].strip() or "unmapped"
            agg.setdefault(key, np.zeros(len(columns)))
            agg[key] += data[i]
        keys = sorted(agg)
        mat = np.vstack([agg[k] for k in keys]) if keys else np.zeros((0, len(columns)))
        if ctx.step_params.get("relative", False):
            total = mat.sum(axis=0)
            mat = np.divide(mat, total, out=np.zeros_like(mat), where=total > 0)
        out = matrix_form(keys, columns, mat, {"n_input_rows": len(names), "relative": bool(ctx.step_params.get("relative", False))})
        ctx[ctx.step_params["output"]] = out
        return None

