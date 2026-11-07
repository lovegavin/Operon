"""Haplotype blocks from adjacent linkage disequilibrium"""
import numpy as np
from src.core import Form
from src.task.step.base import Step
from src.task.step.steps._b55_common import numeric_column, row_names, string_column, table


class HaplotypeBlocksStep(Step):
    parameters_file = "haplotype_blocks.HaplotypeBlocksStep.parameters.json"

    definition = {
        "id": "haplotype_blocks",
        "version": "1.0.0",
        "title": "Haplotype blocks from adjacent linkage disequilibrium",
        "description": "Haplotype blocks from adjacent linkage disequilibrium",
        "category": "Population genetics",
        "icon": "Table",
        "protocol_version": 3,
        "protocol_revision": "3.7",
        "kind": "operator",
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
                        {
                            "param": "row_dim",
                            "default": "row"
                        },
                        {
                            "param": "field_dim",
                            "default": "field"
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
                    "info_open": True,
                    "axis_info_open": True
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
        }
    }

    def run(self, ctx, inputs):
        names = row_names(inputs[0])
        pos = numeric_column(inputs[0], inputs[0].dims[1], "pos")
        r2 = numeric_column(inputs[0], inputs[0].dims[1], "r2_prev")
        thr = float(ctx.step_params.get("r2_threshold", 0.5))
        rows, vals = [], []
        start = 0
        block = 1
        for i in range(1, len(names) + 1):
            if i == len(names) or r2[i] < thr:
                seg = pos[start:i]
                rows.append("block%d" % block)
                vals.append([seg.min(), seg.max(), float(i - start),
                             float(np.mean(np.minimum(r2[start:i], 1.0)))])
                block += 1
                start = i
        ctx[ctx.step_params["output"]] = table(rows, vals, ["start", "end", "n_variants", "mean_r2"])
        return None
