"""Conserved gene order between two genomes"""
import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b71b_common import column, names, table

class ConservedGeneOrderStep(Step):
    parameters_file = "conserved_gene_order.ConservedGeneOrderStep.parameters.json"

    definition = {
        "id": "conserved_gene_order",
        "version": "1.0.0",
        "title": "Conserved gene order between two genomes",
        "description": "Conserved gene order between two genomes",
        "category": "Comparative genomics",
        "icon": "Table",
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "kind": "operator",
        "inputs_arity": 1,
        "output_parameter": "output",
        "outputs": [],
        "contracts": {
            "version": 1,
            "inputs": [{
                "version": 1,
                "numeric": True,
                "dims": [
                    {"param": "row_dim", "default": "gene"},
                    {"param": "field_dim", "default": "field"}
                ],
                "labels": [],
                "parallel": [],
                "ndim": 2
            }],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
        },
        "data_formats": {
            "inputs": [{"logical_type": "form", "representations": ["form"]}],
            "outputs": [{"logical_type": "form", "representations": ["form"]}]
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False, "estimate": "estimate_memory"}
    }

    def run(self, ctx, inputs):
        genes = names(inputs[0], "gene")
        a = column(inputs[0], "gene", "g1_position")
        b = column(inputs[0], "gene", "g2_position")
        ra = np.argsort(np.argsort(a)).astype(float)
        rb = np.argsort(np.argsort(b)).astype(float)
        ra -= ra.mean(); rb -= rb.mean()
        denom = float(np.sqrt((ra ** 2).sum() * (rb ** 2).sum()))
        rho = float((ra * rb).sum() / denom) if denom > 0 else 0.0
        order = np.argsort(a)
        inversions = 0
        seq = b[order]
        for i in range(len(seq)):
            for j in range(i + 1, len(seq)):
                if seq[j] < seq[i]:
                    inversions += 1
        total_pairs = len(seq) * (len(seq) - 1) / 2 if len(seq) > 1 else 1
        data = [[rho, float(len(genes)), float(inversions), inversions / total_pairs]]
        ctx[ctx.step_params["output"]] = table(["genome_pair"], ["spearman", "n_genes", "n_inversions", "frac_inversions"], data)
        return None

