"""Rearrangement breakpoints between two genomes"""
import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b71b_common import column, names, table

class GenomeRearrangementStep(Step):
    parameters_file = "genome_rearrangement.GenomeRearrangementStep.parameters.json"

    definition = {
        "id": "genome_rearrangement",
        "version": "1.0.0",
        "title": "Rearrangement breakpoints between two genomes",
        "description": "Rearrangement breakpoints between two genomes",
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
        order = np.argsort(a)
        ids = [genes[i] for i in order]
        pos2 = {genes[i]: b[i] for i in range(len(genes))}
        preserved = 0
        longest = 1 if genes else 0
        run = 1
        for i in range(len(ids) - 1):
            if pos2[ids[i + 1]] - pos2[ids[i]] == 1:
                preserved += 1
                run += 1
                longest = max(longest, run)
            else:
                run = 1
        adj = max(len(ids) - 1, 1)
        data = [[preserved / adj, float(adj - preserved), float(preserved), float(longest)]]
        ctx[ctx.step_params["output"]] = table(["genome_pair"], ["frac_preserved", "n_breakpoints", "n_preserved", "longest_block"], data)
        return None

