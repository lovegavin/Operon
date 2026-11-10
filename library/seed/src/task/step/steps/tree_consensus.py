import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._tree_common import parse_newick, leaves, path_lengths, tips_path, numeric_column, result_form, text_column


class TreeConsensusStep(Step):
    parameters_file = "tree_consensus.TreeConsensusStep.parameters.json"
    definition = {'id': 'tree_consensus', 'version': '1.0.0', 'title': 'Tree split consensus', 'description': 'Support of clades across a set of trees.', 'category': 'Phylogenetics', 'icon': 'tree', 'kind': 'operator', 'protocol_version': 3, 'protocol_revision': '3.7', 'inputs_arity': 1, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'dims': ['row', 'field'], 'schema': {'type': 'object', 'additionalProperties': True}}], 'output': {'mode': 'declare', 'schema': {'type': 'object', 'additionalProperties': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form']}], 'outputs': [{'logical_type': 'form', 'representations': ['form']}]}}

    def run(self, ctx, inputs):
        form = inputs[0]
        field = form.dims[1]
        idx = (form.labels.get(field) or {}).get("tree", 0)
        texts = text_column(form, field, "tree")
        rows = [str(x) for x in (form.labels.get(form.dims[0]) or {})]
        if len(rows) != len(texts):
            rows = [f"tree{i}" for i in range(len(texts))]
        counts = {}
        total = 0
        for text in texts:
            root = parse_newick(text)
            taxa = sorted(l.name for l in leaves(root))
            n = len(taxa)
            seen = set()
            def walk(node, is_root=False):
                if not node.children:
                    return {node.name}
                clade = set()
                for c in node.children:
                    clade |= walk(c)
                if not is_root and 0 < len(clade) < n:
                    side = tuple(sorted(clade)) if len(clade) * 2 <= n else tuple(sorted(set(taxa) - clade))
                    seen.add(side)
                return clade
            walk(root, True)
            for s in seen:
                counts[s] = counts.get(s, 0) + 1
            total += 1
        names = []
        vals = []
        for s, c in sorted(counts.items()):
            names.append("|".join(s))
            vals.append([c / total, float(c), float(len(s))])
        ctx[ctx.step_params["output"]] = result_form(names, vals, ["support", "count", "size"])
