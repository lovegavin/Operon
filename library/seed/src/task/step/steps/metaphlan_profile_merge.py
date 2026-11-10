import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b58b_common import matrix_form, strings




class MetaphlanProfileMergeStep(Step):

    definition = {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "metaphlan_profile_merge",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Merge two MetaPhlAn profiles",
        "category": "Metagenomics",
        "icon": "Table",
        "description": "Union taxa from two profiles and concatenate their sample columns.",
        "inputs_arity": 2,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [{
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "taxon_dim", "default": "taxon"},
                        {"param": "sample_dim", "default": "sample"}
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2
                }, {
                    "version": 1,
                    "numeric": True,
                    "dims": [
                        {"param": "taxon_dim", "default": "taxon"},
                        {"param": "sample_dim", "default": "sample"}
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2
                }],
            "output": {
                "mode": "declare",
                "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}
            }
        },
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"]}, {"logical_type": "form", "representations": ["form"]}],
            "outputs": [{"logical_type": "form", "representations": ["form"]}]
        },
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": False,
            "estimate": "estimate_memory"
        }
    }
    parameters_file = "metaphlan_profile_merge.MetaphlanProfileMergeStep.parameters.json"

    def run(self, ctx, inputs):
        a_names = strings(inputs[0], "taxon")
        b_names = strings(inputs[1], "taxon")
        a_cols = [k for k, _ in sorted((inputs[0].labels.get("sample", {}) or {}).items(), key=lambda kv: kv[1])]
        b_cols = [k for k, _ in sorted((inputs[1].labels.get("sample", {}) or {}).items(), key=lambda kv: kv[1])]
        names = sorted(set(a_names) | set(b_names))
        cols = ["A:" + c for c in a_cols] + list(b_cols)
        data = np.zeros((len(names), len(cols)))
        index = {n: i for i, n in enumerate(names)}
        for j, c in enumerate(a_cols):
            for i, n in enumerate(a_names):
                data[index[n], j] = inputs[0].data[i, j]
        for j, c in enumerate(b_cols):
            col = len(a_cols) + j
            for i, n in enumerate(b_names):
                data[index[n], col] = inputs[1].data[i, j]
        out = matrix_form(names, cols, data, {"n_merged_taxa": len(names)})
        ctx[ctx.step_params["output"]] = out
        return None

