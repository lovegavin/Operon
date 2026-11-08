"""Robinson-Foulds distance"""
from __future__ import annotations

import numpy as np

from src.core.forms.form import Form
from src.task.step.base import Step
from src.task.step.steps._b79_common import strings, table
from src.task.step.steps._phylo_common import parse_newick, tips


def definition(category, arity, outputs_dims):
    return {
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "id": "tree_robinson_foulds",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Robinson-Foulds distance",
        "description": "Compute the Robinson-Foulds distance between two Newick trees with identical taxon sets.",
        "category": category,
        "icon": "Tree",
        "inputs_arity": arity,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1, "numeric": False, "ndim": 2,
                    "dims": [{"param": "row_dim", "default": "row"},
                             {"param": "field_dim", "default": "field"}],
                    "labels": [], "parallel": [],
                }
                for _ in range(arity)
            ],
            "output": {
                "mode": "declare",
                "schema": {"ndim": outputs_dims, "numeric": True,
                           "info_open": True, "axis_info_open": True},
            },
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False,
                      "estimate": "estimate_memory"},
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}
                       for _ in range(arity)],
            "outputs": [{"logical_type": "form", "representations": ["form"], "metadata": {}}],
        },
    }


class TreeRobinsonFouldsStep(Step):
    parameters_file = "tree_robinson_foulds.TreeRobinsonFouldsStep.parameters.json"

    definition = {'protocol_version': 3, 'protocol_revision': '3.7', 'id': 'tree_robinson_foulds', 'version': '1.0.0', 'kind': 'operator', 'title': 'Robinson-Foulds distance', 'description': 'Compute the Robinson-Foulds distance between two Newick trees with identical taxon sets.', 'category': 'Phylogenetics', 'icon': 'Tree', 'inputs_arity': 2, 'output_parameter': 'output', 'outputs': [], 'contracts': {'version': 1, 'inputs': [{'version': 1, 'numeric': False, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}, {'version': 1, 'numeric': False, 'ndim': 2, 'dims': [{'param': 'row_dim', 'default': 'row'}, {'param': 'field_dim', 'default': 'field'}], 'labels': [], 'parallel': []}], 'output': {'mode': 'declare', 'schema': {'ndim': 2, 'numeric': True, 'info_open': True, 'axis_info_open': True}}}, 'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'}, 'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}, {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}], 'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]}}


    def run(self, ctx, inputs):
        params = ctx.step_params
        out_name = str(params.get("output", "rf"))
        tree_a = parse_newick(strings(inputs[0], "newick")[0])
        tree_b = parse_newick(strings(inputs[1], "newick")[0])
        taxa_a = {tip.name for tip in tips(tree_a)}
        taxa_b = {tip.name for tip in tips(tree_b)}
        if taxa_a != taxa_b:
            raise ValueError("trees do not share the same taxon set")
        n = len(taxa_a)
        splits_a = self._splits(tree_a, taxa_a)
        splits_b = self._splits(tree_b, taxa_a)
        rf = len(splits_a.symmetric_difference(splits_b))
        max_rf = 2 * (n - 3) if n > 3 else 0
        values = [float(rf), float(max_rf), (rf / max_rf) if max_rf else 0.0,
                  float(n), float(len(splits_a)), float(len(splits_b))]
        columns = ["rf", "max_rf", "normalized_rf", "n_taxa", "n_splits_a", "n_splits_b"]
        ctx[out_name] = table(["robinson_foulds"], [values], columns)


    def run(self, ctx, inputs):
        params = ctx.step_params
        out_name = str(params.get("output", "rf"))
        tree_a = parse_newick(strings(inputs[0], "newick")[0])
        tree_b = parse_newick(strings(inputs[1], "newick")[0])
        taxa_a = {tip.name for tip in tips(tree_a)}
        taxa_b = {tip.name for tip in tips(tree_b)}
        if taxa_a != taxa_b:
            raise ValueError("trees do not share the same taxon set")
        n = len(taxa_a)
        splits_a = self._splits(tree_a, taxa_a)
        splits_b = self._splits(tree_b, taxa_a)
        rf = len(splits_a.symmetric_difference(splits_b))
        max_rf = 2 * (n - 3) if n > 3 else 0
        values = [float(rf), float(max_rf), (rf / max_rf) if max_rf else 0.0,
                  float(n), float(len(splits_a)), float(len(splits_b))]
        columns = ["rf", "max_rf", "normalized_rf", "n_taxa", "n_splits_a", "n_splits_b"]
        ctx[out_name] = table(["robinson_foulds"], [values], columns)

    @staticmethod
    def _splits(tree, taxa):
        all_taxa = frozenset(taxa)
        found = set()

        def collect(node):
            if not node.children:
                return frozenset([node.name])
            below = frozenset()
            for child in node.children:
                below |= collect(child)
            if 1 < len(below) < len(all_taxa) - 1:
                other = all_taxa - below
                key = min(below, other)
                found.add(frozenset(key))
            return below

        collect(tree)
        return found
        return splits_a if False else None
