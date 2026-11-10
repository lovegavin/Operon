"""Operon operator tree_mrca."""
from src.core import Form
from src.task.step.base import Step
from ._tree_common import parse_newick, tips_path, path_lengths, descendants, numeric_column, result_form


class TreeMrcaStep(Step):
    definition = {
    "protocol_version": 3,
    "id": "tree_mrca",
    "version": "1.0.0",
    "kind": "operator",
    "protocol_revision": "3.7",
    "title": "Most recent common ancestor of two tips",
    "category": "Phylogenetics",
    "description": "Finds the MRCA node of two tip labels in a Newick tree and reports its height and pairwise distance.",
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

    parameters_file = "tree_mrca.TreeMrcaStep.parameters.json"

    def run(self, ctx, inputs):
        params = ctx.step_params

        root = parse_newick(str(params.get("newick", "")))
        a = str(params.get("taxon_a", ""))
        b = str(params.get("taxon_b", ""))
        pa = tips_path(root, a)
        pb = tips_path(root, b)
        if not pa or not pb:
            raise ValueError("both taxa must be leaves of the tree")
        common = []
        for x, y in zip(pa, pb):
            if x is y:
                common.append(x)
            else:
                break
        mrca = common[-1]
        heights = path_lengths(root)
        depth = 0.0
        for n in common:
            depth += n.length
        dist = heights[a] + heights[b] - 2.0 * depth
        rows = [[float(depth), float(dist), float(len(descendants(mrca))), float(len(pa) + len(pb) - 2 * len(common))]]
        ctx[params["output"]] = result_form(["mrca"], rows, ["height", "tip_distance", "n_descendant_tips", "n_edges"])
        return None

