"""Operon operator tree_parsimony_score."""
from src.core import Form
from src.task.step.base import Step
from ._tree_common import parse_newick, tips_path, path_lengths, descendants, numeric_column, result_form


class TreeParsimonyScoreStep(Step):
    definition = {
    "protocol_version": 3,
    "id": "tree_parsimony_score",
    "version": "1.0.0",
    "kind": "operator",
    "protocol_revision": "3.7",
    "title": "Fitch parsimony score of a tree and character matrix",
    "category": "Phylogenetics",
    "description": "Computes the Fitch parsimony score for a Newick tree and a tip-by-character matrix.",
    "contracts": {
        "version": 1,
        "inputs": [
            {
                "version": "1.0.0",
                "dims": [
                    {
                        "param": "taxon_dim",
                        "default": "taxon"
                    },
                    {
                        "param": "character_dim",
                        "default": "character"
                    }
                ],
                "labels": [],
                "parallel": [],
                "ndim": 2
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
    },
    "resources": {
        "memory_modes": [
            "full"
        ],
        "supports_cuda": False,
        "estimate": "estimate_memory"
    },
    "inputs_arity": 1,
    "outputs": [],
    "output_parameter": "output"
}

    parameters_file = "tree_parsimony_score.TreeParsimonyScoreStep.parameters.json"

    def run(self, ctx, inputs):
        params = ctx.step_params

        root = parse_newick(str(params.get("newick", "")))
        form = inputs[0]
        taxon_axis = "taxon"
        char_axis = form.dims[1]
        names = sorted(form.labels[taxon_axis], key=lambda k: form.labels[taxon_axis][k])
        mat = form.data
        total = 0.0
        informative = 0
        for j in range(mat.shape[1]):
            states = {}
            for i, name in enumerate(names):
                if name in form.labels[taxon_axis]:
                    states[name] = frozenset([int(round(mat[i, j]))])
            def fitch(node):
                nonlocal total
                if not node.children:
                    return states.get(node.name, frozenset())
                child_sets = [fitch(c) for c in node.children]
                inter = set.intersection(*[set(s) for s in child_sets]) if child_sets else set()
                if inter:
                    return frozenset(inter)
                union = set().union(*[set(s) for s in child_sets]) if child_sets else set()
                total += 1.0
                return frozenset(union)
            fitch(root)
            vals = [v for v in states.values()]
            if len(vals) > 1 and len(set().union(*[set(v) for v in vals])) > 1:
                counts = {}
                for s in vals:
                    for x in s:
                        counts[x] = counts.get(x, 0) + 1
                if len(counts) >= 2 and min(counts.values()) >= 2:
                    informative += 1
        rows = [[float(total), float(mat.shape[1]), float(informative)]]
        ctx[params["output"]] = result_form(["tree"], rows, ["parsimony_score", "n_characters", "n_informative"])
        return None

