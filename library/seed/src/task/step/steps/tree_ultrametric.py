"""Operon operator tree_ultrametric."""
from src.core import Form
from src.task.step.base import Step
from ._tree_common import parse_newick, tips_path, path_lengths, descendants, numeric_column, result_form


class TreeUltrametricStep(Step):
    definition = {
    "protocol_version": 3,
    "id": "tree_ultrametric",
    "version": "1.0.0",
    "kind": "operator",
    "protocol_revision": "3.7",
    "title": "Ultrametricity check for a dated tree",
    "category": "Phylogenetics",
    "description": "Tests whether all root-to-tip distances are equal within a tolerance.",
    "contracts": {
        "version": 1,
        "inputs": [],
        "output": {
            "mode": "declare",
            "schema": {
                "ndim": 2,
                "numeric": True,
                "info_open": True
            }
        }
    },
    "data_formats": {
        "inputs": [],
        "outputs": [
            {
                "logical_type": "form",
                "representations": [
                    "form"
                ]
            }
        ]
    },
    "resources": {
        "memory_modes": [
            "full"
        ],
        "supports_cuda": False,
        "estimate": "estimate_memory"
    },
    "inputs_arity": 0,
    "outputs": [],
    "output_parameter": "output"
}

    parameters_file = "tree_ultrametric.TreeUltrametricStep.parameters.json"

    def run(self, ctx, inputs):
        params = ctx.step_params

        root = parse_newick(str(params.get("newick", "")))
        heights = path_lengths(root)
        vals = list(heights.values())
        if not vals:
            raise ValueError("tree has no tips")
        lo = min(vals)
        hi = max(vals)
        mean = sum(vals) / len(vals)
        cv = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5 / mean if mean else 0.0
        tol = float(params.get("tolerance", 1e-6))
        rows = [[1.0 if hi - lo <= tol else 0.0, float(hi - lo), float(lo), float(hi), float(cv)]]
        ctx[params["output"]] = result_form(["tree"], rows, ["is_ultrametric", "range", "min_height", "max_height", "cv"])
        return None

